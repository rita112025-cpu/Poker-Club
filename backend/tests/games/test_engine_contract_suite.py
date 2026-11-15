"""P2-F: run the shared contract suite, prove it catches broken engines, and show the
Protocol is payload-agnostic (extension point for future games such as Chinese poker).

No Chinese poker rules exist in the specs; ArrangementEngine is a neutral stub with an
arbitrary payload type, used only to show the contract and suite do not assume one
payload shape. Not applicable: rule legality, real engines, transport.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from uuid import UUID

import pytest
from engine_contract_suite import ContractScenario, check_engine_contract
from test_engine_contract import StubEngine, StubPayload

from app.games.core import (
    ActionValidation,
    ApplyResult,
    Card,
    Deck,
    EngineRegistration,
    EngineRegistry,
    EventVisibility,
    GameAction,
    GameConfig,
    GameEngine,
    GameError,
    GameEvent,
    GameResult,
    GameState,
    GameStatus,
    Player,
    PlayerResult,
    PlayerView,
    PrivateGameData,
    PrivatePlayerData,
)

ALICE, BOB = UUID(int=1), UUID(int=2)
SESSION = UUID(int=3)
PLAYERS = (Player(ALICE, "Alice", 0, 100), Player(BOB, "Bob", 1, 100))
CONFIG = GameConfig("stub", "1")


def _action(state: GameState, player: UUID, version: int | None = None) -> GameAction:
    current = state.public.state_version if version is None else version
    return GameAction(player, UUID(int=1000 + current), current, "move")


def _turn_player(state: GameState) -> UUID:
    turn = state.public.turn
    return turn.player_id if turn is not None else ALICE


def _other(state: GameState) -> UUID:
    return BOB if _turn_player(state) == ALICE else ALICE


def stub_scenario() -> ContractScenario[StubPayload]:
    def next_legal(state: GameState) -> tuple[GameAction, StubPayload] | None:
        if state.public.status is GameStatus.FINISHED:
            return None
        return _action(state, _turn_player(state)), StubPayload(1)

    return ContractScenario(
        CONFIG,
        SESSION,
        PLAYERS,
        next_legal,
        illegal=lambda s: (_action(s, _other(s)), StubPayload(1)),
        stale=lambda s: (
            _action(s, _turn_player(s), s.public.state_version + 5),
            StubPayload(1),
        ),
        after_over=lambda s: (_action(s, ALICE), StubPayload(1)),
    )


def test_a_conforming_engine_passes_the_contract_suite() -> None:
    check_engine_contract(StubEngine(), stub_scenario())


# ---- the suite must catch deliberately broken engines ------------------------


class AcceptsTestOnlyDeck(StubEngine):
    def create_game(
        self, config: GameConfig, session_id: UUID, players: tuple[Player, ...], deck: Deck
    ) -> GameState | GameError:
        return super().create_game(config, session_id, players, Deck())


class SkipsVersion(StubEngine):
    def apply_action(
        self, state: GameState, action: GameAction, payload: StubPayload
    ) -> ApplyResult | GameError:
        out = super().apply_action(state, action, payload)
        if isinstance(out, ApplyResult):
            bumped = replace(out.state.public, state_version=out.state.public.state_version + 1)
            return ApplyResult(replace(out.state, public=bumped), out.events)
        return out


class ReusesEventSeq(StubEngine):
    def apply_action(
        self, state: GameState, action: GameAction, payload: StubPayload
    ) -> ApplyResult | GameError:
        out = super().apply_action(state, action, payload)
        if isinstance(out, ApplyResult):
            return ApplyResult(out.state, (GameEvent(0, "moved", EventVisibility.PUBLIC),))
        return out


class ViewHasOtherHand(StubEngine):
    def get_player_view(self, state: GameState, viewer_id: UUID) -> PlayerView | GameError:
        view = super().get_player_view(state, viewer_id)
        if isinstance(view, PlayerView):
            other = next(p for p in state.private.players if p.player_id != viewer_id)
            return PlayerView(viewer_id, view.public, PrivatePlayerData(viewer_id, other.hand))
        return view


class ViewHasRemainingCard(StubEngine):
    def get_player_view(self, state: GameState, viewer_id: UUID) -> PlayerView | GameError:
        view = super().get_player_view(state, viewer_id)
        if isinstance(view, PlayerView):
            extra = (*view.private.hand, state.private.remaining_cards[0])
            return PlayerView(viewer_id, view.public, PrivatePlayerData(viewer_id, extra))
        return view


class OutsiderGetsView(StubEngine):
    def get_player_view(self, state: GameState, viewer_id: UUID) -> PlayerView | GameError:
        view = super().get_player_view(state, viewer_id)
        if isinstance(view, GameError):
            return super().get_player_view(state, ALICE)
        return view


class AcceptsWrongTurn(StubEngine):
    def validate_action(
        self, state: GameState, action: GameAction, payload: StubPayload
    ) -> ActionValidation:
        return ActionValidation()

    def apply_action(
        self, state: GameState, action: GameAction, payload: StubPayload
    ) -> ApplyResult | GameError:
        if state.public.turn is None:
            return super().apply_action(state, action, payload)
        fixed = replace(
            action, player_id=state.public.turn.player_id, state_version=state.public.state_version
        )
        return super().apply_action(state, fixed, payload)


class ResultBeforeGameOver(StubEngine):
    def calculate_result(self, state: GameState) -> GameResult | GameError:
        return GameResult((PlayerResult(ALICE, 0, 1), PlayerResult(BOB, 0, 1)))


class ResultMissingPlayer(StubEngine):
    def calculate_result(self, state: GameState) -> GameResult | GameError:
        out = super().calculate_result(state)
        return GameResult((PlayerResult(ALICE, 0, 1),)) if isinstance(out, GameResult) else out


class ChangesGameType(StubEngine):
    def apply_action(
        self, state: GameState, action: GameAction, payload: StubPayload
    ) -> ApplyResult | GameError:
        out = super().apply_action(state, action, payload)
        if isinstance(out, ApplyResult):
            return ApplyResult(replace(out.state, game_type="other"), out.events)
        return out


class DuplicatesACard(StubEngine):
    def create_game(
        self, config: GameConfig, session_id: UUID, players: tuple[Player, ...], deck: Deck
    ) -> GameState | GameError:
        out = super().create_game(config, session_id, players, deck)
        if isinstance(out, GameState):
            dup = out.private.players[0].hand[0]
            private = PrivateGameData(out.private.players, (dup, *out.private.remaining_cards))
            return replace(out, private=private)
        return out


class NewGameAlreadyOver(StubEngine):
    def is_game_over(self, state: GameState) -> bool:
        return True


class NeverGameOver(StubEngine):
    def is_game_over(self, state: GameState) -> bool:
        return False


class LeaksCardInValidationError(StubEngine):
    def validate_action(
        self, state: GameState, action: GameAction, payload: StubPayload
    ) -> ActionValidation:
        out = super().validate_action(state, action, payload)
        if out.error is not None:
            hidden = state.private.players[1].hand[0]
            return ActionValidation(
                GameError(out.error.code, f"not allowed, Bob holds {hidden.code}")
            )
        return out


class LeaksCardInResultError(StubEngine):
    def calculate_result(self, state: GameState) -> GameResult | GameError:
        out = super().calculate_result(state)
        if isinstance(out, GameError):
            return GameError(
                out.code, f"unfinished; deck top is {state.private.remaining_cards[0]!r}"
            )
        return out


class LeaksCardInViewError(StubEngine):
    def get_player_view(self, state: GameState, viewer_id: UUID) -> PlayerView | GameError:
        out = super().get_player_view(state, viewer_id)
        if isinstance(out, GameError):
            return GameError(
                out.code, f"unknown viewer; Alice holds {state.private.players[0].hand[0].code}."
            )
        return out


class NondeterministicApply(StubEngine):
    calls = 0

    def apply_action(
        self, state: GameState, action: GameAction, payload: StubPayload
    ) -> ApplyResult | GameError:
        out = super().apply_action(state, action, payload)
        if isinstance(out, ApplyResult):
            type(self).calls += 1
            event = GameEvent(type(self).calls, "moved", EventVisibility.PUBLIC)
            return ApplyResult(out.state, (event,))
        return out


class NondeterministicResult(StubEngine):
    calls = 0

    def calculate_result(self, state: GameState) -> GameResult | GameError:
        out = super().calculate_result(state)
        if isinstance(out, GameResult):
            type(self).calls += 1
            return GameResult(
                (PlayerResult(ALICE, type(self).calls, 1), PlayerResult(BOB, -type(self).calls, 2))
            )
        return out


class AcceptsAfterGameOverForAlice(StubEngine):
    def validate_action(
        self, state: GameState, action: GameAction, payload: StubPayload
    ) -> ActionValidation:
        if state.public.status is GameStatus.FINISHED and action.player_id == ALICE:
            return ActionValidation()
        return super().validate_action(state, action, payload)

    def apply_action(
        self, state: GameState, action: GameAction, payload: StubPayload
    ) -> ApplyResult | GameError:
        if state.public.status is GameStatus.FINISHED and action.player_id == ALICE:
            return ApplyResult(state, ())
        return super().apply_action(state, action, payload)


BROKEN: list[tuple[str, Callable[[], StubEngine]]] = [
    ("accepts test-only deck", AcceptsTestOnlyDeck),
    ("skips a version", SkipsVersion),
    ("reuses event seq", ReusesEventSeq),
    ("view has another hand", ViewHasOtherHand),
    ("view has a remaining card", ViewHasRemainingCard),
    ("non-member gets a view", OutsiderGetsView),
    ("accepts wrong turn and stale version", AcceptsWrongTurn),
    ("result before game over", ResultBeforeGameOver),
    ("result misses a player", ResultMissingPlayer),
    ("changes game type", ChangesGameType),
    ("duplicates a card", DuplicatesACard),
    ("new game already over", NewGameAlreadyOver),
    ("never game over", NeverGameOver),
    ("leaks a hidden card in a validation error", LeaksCardInValidationError),
    ("leaks a deck card in a result error", LeaksCardInResultError),
    ("leaks a hidden card in a view error", LeaksCardInViewError),
    ("apply_action is not deterministic", NondeterministicApply),
    ("calculate_result is not repeatable", NondeterministicResult),
    ("accepts an action after game over", AcceptsAfterGameOverForAlice),
]


@pytest.mark.parametrize("name,engine_type", BROKEN, ids=[name for name, _ in BROKEN])
def test_suite_rejects_broken_engines(name: str, engine_type: Callable[[], StubEngine]) -> None:
    with pytest.raises(AssertionError):
        check_engine_contract(engine_type(), stub_scenario())


# ---- payload-agnostic extension point ---------------------------------------


@dataclass(frozen=True, slots=True)
class ArrangementPayload:
    groups: tuple[tuple[Card, ...], ...]


class ArrangementEngine:
    """Neutral stub with a non-integer payload; delegates to StubEngine for state handling."""

    def __init__(self) -> None:
        self._inner = StubEngine()

    @staticmethod
    def _convert(payload: ArrangementPayload) -> StubPayload:
        return StubPayload(len(payload.groups))

    def create_game(
        self, config: GameConfig, session_id: UUID, players: tuple[Player, ...], deck: Deck
    ) -> GameState | GameError:
        return self._inner.create_game(config, session_id, players, deck)

    def validate_action(
        self, state: GameState, action: GameAction, payload: ArrangementPayload
    ) -> ActionValidation:
        return self._inner.validate_action(state, action, self._convert(payload))

    def apply_action(
        self, state: GameState, action: GameAction, payload: ArrangementPayload
    ) -> ApplyResult | GameError:
        return self._inner.apply_action(state, action, self._convert(payload))

    def get_player_view(self, state: GameState, viewer_id: UUID) -> PlayerView | GameError:
        return self._inner.get_player_view(state, viewer_id)

    def is_game_over(self, state: GameState) -> bool:
        return self._inner.is_game_over(state)

    def calculate_result(self, state: GameState) -> GameResult | GameError:
        return self._inner.calculate_result(state)


def test_protocol_and_suite_accept_a_different_payload_type() -> None:
    engine: GameEngine[ArrangementPayload] = ArrangementEngine()  # checked by mypy
    payload = ArrangementPayload(((Card.from_code("AS"),),))

    def next_legal(state: GameState) -> tuple[GameAction, ArrangementPayload] | None:
        if state.public.status is GameStatus.FINISHED:
            return None
        return _action(state, _turn_player(state)), payload

    scenario = ContractScenario(
        CONFIG,
        SESSION,
        PLAYERS,
        next_legal,
        illegal=lambda s: (_action(s, _other(s)), payload),
        stale=lambda s: (_action(s, _turn_player(s), s.public.state_version + 5), payload),
        after_over=lambda s: (_action(s, ALICE), payload),
    )
    check_engine_contract(engine, scenario)


def test_unimplemented_games_cannot_be_looked_up_or_enabled() -> None:
    registry = EngineRegistry()
    entry = EngineRegistration("arrangement_stub", "1", 2, 4, ArrangementEngine())
    assert registry.register(entry) is None
    for code in ("chinese_poker", "five_card_draw", "texas_holdem", "big_two"):
        assert not registry.is_registered(code)
        assert isinstance(registry.get(code), GameError)
    assert registry.codes() == ("arrangement_stub",)


def test_phase_one_catalog_still_seeds_every_game_as_disabled() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / "migrations" / "versions" / "0001_game_types.py").read_text(encoding="utf-8")
    assert '"enabled": False' in text and '"enabled": True' not in text
    assert '"chinese_poker"' in text
