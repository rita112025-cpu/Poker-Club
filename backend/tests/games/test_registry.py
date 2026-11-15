"""P2-D: in-memory engine registry contract.

FakeEngine below exists only in tests to satisfy the runtime method check; it is not a
game. Not applicable: database enabled flags (the registry deliberately has none),
thread safety (registration is startup-only and documented as such).
"""

import ast
from pathlib import Path
from typing import Any, cast

import pytest

from app.games.core import (
    DUPLICATE_GAME,
    ENGINE_METHODS,
    UNKNOWN_GAME,
    EngineRegistration,
    EngineRegistry,
    GameError,
)

CATALOG_CODES = ("texas_holdem", "big_two", "chinese_poker", "five_card_draw")


class TextWithSecret(str):
    secret: str = "REGISTRY_SECRET_5q"


class IntWithSecret(int):
    secret: str = "REGISTRY_SECRET_5q"


class FakeEngine:
    def create_game(self, *args: object) -> None: ...
    def validate_action(self, *args: object) -> None: ...
    def apply_action(self, *args: object) -> None: ...
    def get_player_view(self, *args: object) -> None: ...
    def is_game_over(self, *args: object) -> None: ...
    def calculate_result(self, *args: object) -> None: ...


def registration(code: str = "fake_game", **overrides: Any) -> EngineRegistration:
    fields: dict[str, Any] = {
        "code": code,
        "rules_version": "1",
        "min_players": 2,
        "max_players": 4,
        "engine": FakeEngine(),
    }
    fields.update(overrides)
    return EngineRegistration(**fields)


def test_new_registry_is_empty_and_catalog_games_are_not_registered() -> None:
    registry = EngineRegistry()
    assert len(registry) == 0 and registry.codes() == () and registry.registrations() == ()
    for code in CATALOG_CODES:
        assert not registry.is_registered(code)
        assert registry.get(code) == GameError(UNKNOWN_GAME, "Unknown game")


def test_register_and_lookup_round_trip() -> None:
    registry = EngineRegistry()
    entry = registration("big_two", max_players=4)
    assert registry.register(entry) is None
    assert registry.is_registered("big_two")
    assert registry.get("big_two") is entry
    assert registry.codes() == ("big_two",) and len(registry) == 1


def test_duplicate_code_returns_error_and_keeps_original() -> None:
    registry = EngineRegistry()
    first = registration("big_two", rules_version="1")
    registry.register(first)
    error = registry.register(registration("big_two", rules_version="2"))
    assert isinstance(error, GameError) and error.code == DUPLICATE_GAME
    assert registry.get("big_two") is first and len(registry) == 1


def test_unknown_code_returns_error_without_echoing_input() -> None:
    registry = EngineRegistry()
    hostile = "<script>PRIVATE_PROBE</script>"
    error = registry.get(hostile)
    assert isinstance(error, GameError) and error.code == UNKNOWN_GAME
    assert "PRIVATE_PROBE" not in error.message and hostile not in repr(error)
    assert registry.is_registered(hostile) is False


@pytest.mark.parametrize("bad", [123, None, b"big_two", TextWithSecret("big_two")])
def test_lookup_rejects_non_exact_string_codes(bad: object) -> None:
    registry = EngineRegistry()
    with pytest.raises(TypeError, match="game code must be a string"):
        registry.get(cast(str, bad))
    with pytest.raises(TypeError, match="game code must be a string"):
        registry.is_registered(cast(str, bad))


@pytest.mark.parametrize(
    "bad",
    ["", "a", "Big_Two", "big two", "big-two", "1big", " big_two", "big_two\n", "x" * 33, "büg"],
)
def test_registration_rejects_malformed_codes(bad: str) -> None:
    with pytest.raises(ValueError, match="game code"):
        registration(bad)


def test_registration_accepts_boundary_code_lengths() -> None:
    assert registration("ab").code == "ab"
    assert registration("a" * 32).code == "a" * 32


@pytest.mark.parametrize(
    "overrides,error",
    [
        ({"code": TextWithSecret("fake_game")}, TypeError),
        ({"code": 5}, TypeError),
        ({"rules_version": TextWithSecret("1")}, TypeError),
        ({"rules_version": " "}, ValueError),
        ({"min_players": 1}, ValueError),
        ({"min_players": 5, "max_players": 4}, ValueError),
        ({"min_players": IntWithSecret(2)}, TypeError),
        ({"max_players": True}, TypeError),
        ({"min_players": 2.0}, TypeError),
        ({"max_players": -1}, ValueError),
    ],
)
def test_registration_rejects_invalid_metadata(
    overrides: dict[str, Any], error: type[Exception]
) -> None:
    with pytest.raises(error):
        registration(**overrides)


def test_registration_rejects_non_engines() -> None:
    class MissingMethod:
        def create_game(self) -> None: ...

    class NotCallable(FakeEngine):
        apply_action = None  # type: ignore[assignment]

    for method in ENGINE_METHODS:
        engine = FakeEngine()
        setattr(engine, method, 5)
        with pytest.raises(TypeError, match=f"missing a callable {method}"):
            registration(engine=engine)
    with pytest.raises(TypeError, match="missing a callable"):
        registration(engine=MissingMethod())
    with pytest.raises(TypeError, match="missing a callable"):
        registration(engine=NotCallable())
    with pytest.raises(TypeError, match="missing a callable"):
        registration(engine=None)
    with pytest.raises(TypeError, match="instance, not a class"):
        registration(engine=FakeEngine)


def test_register_rejects_non_registration_objects_and_subclasses() -> None:
    registry = EngineRegistry()

    class Extended(EngineRegistration):
        pass

    for bad in (None, {"code": "fake_game"}, "fake_game"):
        with pytest.raises(TypeError, match="exact EngineRegistration"):
            registry.register(cast(EngineRegistration, bad))
    entry = registration()
    sub = Extended(
        entry.code, entry.rules_version, entry.min_players, entry.max_players, entry.engine
    )
    with pytest.raises(TypeError, match="exact EngineRegistration"):
        registry.register(sub)
    assert len(registry) == 0


def test_snapshots_do_not_expose_internal_state() -> None:
    registry = EngineRegistry()
    registry.register(registration("b_game"))
    registry.register(registration("a_game"))
    assert registry.codes() == ("a_game", "b_game")
    assert [r.code for r in registry.registrations()] == ["a_game", "b_game"]
    assert isinstance(registry.codes(), tuple) and isinstance(registry.registrations(), tuple)
    with pytest.raises(AttributeError):
        cast(Any, registry).extra = 1  # __slots__: no stray state
    with pytest.raises(AttributeError):
        cast(Any, registration()).code = "other"  # frozen
    assert "FakeEngine" not in repr(registry)


def test_registries_are_independent_instances() -> None:
    one, two = EngineRegistry(), EngineRegistry()
    one.register(registration("big_two"))
    assert two.codes() == () and not two.is_registered("big_two")


def test_registry_module_has_no_framework_or_database_imports() -> None:
    path = Path(__file__).resolve().parents[2] / "app" / "games" / "core" / "registry.py"
    forbidden = {"fastapi", "starlette", "sqlalchemy", "pydantic", "alembic", "psycopg"}
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    imported = {name.split(".")[0] for name in modules}
    assert not imported & forbidden
    assert not any(name.startswith("app.db") for name in modules)
