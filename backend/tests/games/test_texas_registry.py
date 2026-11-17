"""P3-05: registering the Texas hold'em engine with an EngineRegistry.

The rules values below are TEST FIXTURES: blinds, the burn setting and the chip unit are still
undecided product policy, so the product code offers no default rules and these tests supply
their own. Not applicable here: Room, authentication, transport.
"""

import ast
import inspect
import random
import re
from pathlib import Path
from uuid import UUID

import pytest
from test_texas_engine import act, ext

from app.games.core import (
    DUPLICATE_GAME,
    UNKNOWN_GAME,
    Deck,
    EngineRegistration,
    EngineRegistry,
    GameConfig,
    GameEngine,
    GameError,
    GameState,
    GameStatus,
    Player,
)
from app.games.core.registry import ENGINE_METHODS
from app.games.texas_holdem import (
    TEXAS_CODE,
    TexasEngine,
    TexasPayload,
    TexasRules,
    legal_actions,
    register_texas_holdem,
    texas_registration,
)

RULES = TexasRules("reg-1", 5, 10, False)  # fixture values only
ROOT = Path(__file__).resolve().parents[2]


def catalog_row(code: str) -> tuple[int, int]:
    text = (ROOT / "migrations" / "versions" / "0001_game_types.py").read_text(encoding="utf-8")
    match = re.search(rf'\("{code}",\s*"[^"]*",\s*(\d+),\s*(\d+)\)', text)
    assert match is not None, f"{code} is not in the game_types catalog seed"
    return int(match.group(1)), int(match.group(2))


def players(count: int = 3) -> tuple[Player, ...]:
    return tuple(Player(UUID(int=100 + s), f"p{s}", s, 100) for s in range(count))


def test_the_registration_record_matches_the_game_catalog() -> None:
    entry = texas_registration(RULES)
    assert type(entry) is EngineRegistration
    assert entry.code == TEXAS_CODE == "texas_holdem"
    assert (entry.min_players, entry.max_players) == catalog_row("texas_holdem") == (2, 9)
    assert entry.rules_version == RULES.version
    assert type(entry.engine) is TexasEngine
    assert all(callable(getattr(entry.engine, name)) for name in ENGINE_METHODS)


def test_register_and_look_up_through_the_registry() -> None:
    registry = EngineRegistry()
    assert register_texas_holdem(registry, RULES) is None
    assert registry.is_registered("texas_holdem") and registry.codes() == ("texas_holdem",)
    found = registry.get("texas_holdem")
    assert isinstance(found, EngineRegistration) and found.rules_version == "reg-1"
    assert registry.registrations() == (found,)


def test_a_duplicate_registration_is_an_error_and_keeps_the_first() -> None:
    registry = EngineRegistry()
    assert register_texas_holdem(registry, RULES) is None
    again = register_texas_holdem(registry, TexasRules("reg-2", 1, 2, True))
    assert isinstance(again, GameError) and again.code == DUPLICATE_GAME
    kept = registry.get("texas_holdem")
    assert isinstance(kept, EngineRegistration) and kept.rules_version == "reg-1"
    assert len(registry) == 1


def test_unknown_and_unimplemented_games_stay_unknown() -> None:
    registry = EngineRegistry()
    register_texas_holdem(registry, RULES)
    for code in ("big_two", "chinese_poker", "five_card_draw", "Texas_Holdem", "texas_holdem "):
        assert not registry.is_registered(code)
        error = registry.get(code)
        assert isinstance(error, GameError) and error.code == UNKNOWN_GAME
        assert code not in error.message


def test_registries_are_independent_and_nothing_is_registered_by_default() -> None:
    first, second = EngineRegistry(), EngineRegistry()
    register_texas_holdem(first, RULES)
    assert second.codes() == () and len(second) == 0
    import app.games.core as core_package
    import app.games.texas_holdem as texas_package

    for module in (core_package, texas_package):
        assert not [
            name for name, value in vars(module).items() if isinstance(value, EngineRegistry)
        ], "a module-level registry would be a hidden global"


def test_the_rules_object_must_be_an_exact_texas_rules() -> None:
    class LooseRules(TexasRules):
        pass

    for bad in (None, "rules", {"version": "x"}, LooseRules("x", 1, 2, False)):
        with pytest.raises(TypeError):
            texas_registration(bad)  # type: ignore[arg-type]


def test_the_engine_comes_from_the_registry_and_plays_a_whole_hand() -> None:
    registry = EngineRegistry()
    register_texas_holdem(registry, RULES)
    entry = registry.get("texas_holdem")
    assert isinstance(entry, EngineRegistration)
    engine: GameEngine[TexasPayload] = entry.engine
    config = GameConfig(entry.code, entry.rules_version)
    table = players(4)
    assert entry.min_players <= len(table) <= entry.max_players
    state = engine.create_game(config, UUID(int=1), table, Deck())
    assert isinstance(state, GameState)
    generator = random.Random(7)
    assert isinstance(engine, TexasEngine)
    while state.public.status is GameStatus.IN_PROGRESS:
        legal = legal_actions(state)
        assert legal is not None
        kind = generator.choice([k for k in legal.kinds if k not in ("bet", "raise", "fold")])
        state, _ = act(engine, state, kind)
    assert ext(state).ended is not None and engine.is_game_over(state)


def test_a_configuration_for_another_rules_version_is_refused() -> None:
    entry = texas_registration(RULES)
    wrong = entry.engine.create_game(
        GameConfig("texas_holdem", "other-rules"), UUID(int=1), players(), Deck()
    )
    assert isinstance(wrong, GameError) and wrong.code == "config_mismatch"
    other = entry.engine.create_game(
        GameConfig("big_two", RULES.version), UUID(int=1), players(), Deck()
    )
    assert isinstance(other, GameError) and other.code == "config_mismatch"


def test_the_engine_is_only_built_by_the_registration_helper() -> None:
    """No application module may construct TexasEngine directly (that would bypass the Registry)."""
    app_root = ROOT / "app"
    builders: list[str] = []
    for path in app_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
                if name == "TexasEngine":
                    builders.append(path.relative_to(app_root).as_posix())
    assert builders == ["games/texas_holdem/registration.py"]


def test_registration_helpers_have_exactly_the_documented_signatures() -> None:
    assert list(inspect.signature(texas_registration).parameters) == ["rules"]
    assert list(inspect.signature(register_texas_holdem).parameters) == ["registry", "rules"]
    source = (ROOT / "app" / "games" / "texas_holdem" / "registration.py").read_text(
        encoding="utf-8"
    )
    assert "TexasRules(" not in source.replace("rules: TexasRules", "").replace("TexasRules)", "")
