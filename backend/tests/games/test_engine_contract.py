"""P2-C: engine result-type matrix, deck-source rule and Protocol contract.

The stub engine below exists only in tests to exercise the six-method contract; it is
not a game and is never registered. Not applicable here: real hand evaluation,
betting, transport and authentication (later phases).
"""

import ast
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest

from app.games.core import (
    ActionValidation,
    ApplyResult,
    Card,
    Deck,
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
    PublicGameData,
    TestOnlyDeckError,
    Turn,
    require_production_deck,
)

ALICE = UUID(int=1)
BOB = UUID(int=2)
SESSION = UUID(int=3)
MARKER = "ENGINE_SECRET_MARKER_8z1"


class TextWithSecret(str):
    secret: str = MARKER


class IntWithSecret(int):
    secret: str = MARKER


class UuidWithSecret(UUID):
    secret: str = MARKER


class TupleWithSecret(tuple):  # type: ignore[type-arg]
    secret: str = MARKER


@dataclass(frozen=True, slots=True)
class StubPayload:
    amount: int


class StubEngine:
    """Two-player toy game: players alternate, game ends after three actions."""

    def create_game(
        self,
        config: GameConfig,
        session_id: UUID,
        players: tuple[Player, ...],
        deck: Deck,
    ) -> GameState | GameError:
        if len(players) != 2:
            return GameError("bad_players", "Exactly two players are required")
        require_production_deck(deck)
        private = tuple(PrivatePlayerData(p.id, deck.deal(2)) for p in players)
        remaining = deck.deal(deck.remaining_count)
        return GameState(
            session_id,
            config.game_type,
            config.rules_version,
            PublicGameData(GameStatus.IN_PROGRESS, 0, players, Turn(players[0].id)),
            PrivateGameData(private, remaining),
        )

    def validate_action(
        self, state: GameState, action: GameAction, payload: StubPayload
    ) -> ActionValidation:
        if action.state_version != state.public.state_version:
            return ActionValidation(GameError("stale_state", "State is out of date"))
        if state.public.turn is None or action.player_id != state.public.turn.player_id:
            return ActionValidation(GameError("not_your_turn", "Not your turn"))
        if payload.amount <= 0:
            return ActionValidation(GameError("bad_amount", "Amount must be positive"))
        return ActionValidation()

    def apply_action(
        self, state: GameState, action: GameAction, payload: StubPayload
    ) -> ApplyResult | GameError:
        check = self.validate_action(state, action, payload)
        if check.error is not None:
            return check.error
        version = state.public.state_version + 1
        ids = [p.id for p in state.public.players]
        done = version >= 3
        nxt = None if done else Turn(ids[version % 2])
        public = replace(
            state.public,
            state_version=version,
            status=GameStatus.FINISHED if done else GameStatus.IN_PROGRESS,
            turn=nxt,
        )
        events = (
            GameEvent(version * 2, "moved", EventVisibility.PUBLIC),
            GameEvent(version * 2 + 1, "dealt_to", EventVisibility.PRIVATE, action.player_id),
        )
        return ApplyResult(replace(state, public=public), events)

    def get_player_view(self, state: GameState, viewer_id: UUID) -> PlayerView | GameError:
        for item in state.private.players:
            if item.player_id == viewer_id:
                return PlayerView(viewer_id, state.public, item)
        return GameError("not_in_game", "Viewer is not in this game")

    def is_game_over(self, state: GameState) -> bool:
        return state.public.status is GameStatus.FINISHED

    def calculate_result(self, state: GameState) -> GameResult | GameError:
        if not self.is_game_over(state):
            return GameError("not_finished", "Game is not finished")
        a, b = (p.id for p in state.public.players)
        return GameResult((PlayerResult(a, 5, 1), PlayerResult(b, -5, 2)))


def new_game() -> tuple[StubEngine, GameState]:
    engine = StubEngine()
    created = engine.create_game(
        GameConfig("stub", "1"),
        SESSION,
        (Player(ALICE, "Alice", 0, 100), Player(BOB, "Bob", 1, 100)),
        Deck(),
    )
    assert isinstance(created, GameState)
    return engine, created


def act(state: GameState, player: UUID) -> GameAction:
    return GameAction(
        player, UUID(int=100 + state.public.state_version), state.public.state_version, "move"
    )


# ---- result-type matrix ----------------------------------------------------


def test_stub_satisfies_protocol_statically() -> None:
    engine: GameEngine[StubPayload] = StubEngine()  # checked by mypy
    assert engine is not None


@pytest.mark.parametrize(
    "build",
    [
        lambda: GameConfig(TextWithSecret("g"), "1"),
        lambda: GameConfig("g", TextWithSecret("1")),
        lambda: GameConfig("g", " "),
        lambda: GameEvent(IntWithSecret(0), "e", EventVisibility.PUBLIC),
        lambda: GameEvent(True, "e", EventVisibility.PUBLIC),
        lambda: GameEvent(0, TextWithSecret("e"), EventVisibility.PUBLIC),
        lambda: GameEvent(0, "e", cast(EventVisibility, "public")),
        lambda: GameEvent(0, "e", EventVisibility.PUBLIC, ALICE),
        lambda: GameEvent(0, "e", EventVisibility.PRIVATE),
        lambda: GameEvent(0, "e", EventVisibility.PRIVATE, UuidWithSecret(int=1)),
        lambda: ActionValidation(cast(GameError, "error")),
        lambda: PlayerResult(UuidWithSecret(int=1), 0, 1),
        lambda: PlayerResult(ALICE, IntWithSecret(0), 1),
        lambda: PlayerResult(ALICE, True, 1),
        lambda: PlayerResult(ALICE, 0, 0),
        lambda: PlayerResult(ALICE, 0, IntWithSecret(1)),
    ],
)
def test_result_type_fields_reject_subclasses_and_invalid_values(build: Any) -> None:
    with pytest.raises((TypeError, ValueError)):
        build()


def test_valid_events_validation_and_results_round_trip_through_asdict() -> None:
    event = GameEvent(4, "moved", EventVisibility.PRIVATE, BOB)
    assert asdict(event)["recipient_id"] == BOB
    assert ActionValidation().is_valid
    assert not ActionValidation(GameError("c", "m")).is_valid
    result = GameResult((PlayerResult(ALICE, 3, 1), PlayerResult(BOB, -3, 2)))
    assert asdict(result)["players"][1] == {"player_id": BOB, "points_delta": -3, "rank": 2}


def test_game_result_rejects_container_subclass_nested_values_and_non_conservation() -> None:
    good = PlayerResult(ALICE, 1, 1)
    with pytest.raises(TypeError, match="result players must be a tuple"):
        GameResult(cast(Any, TupleWithSecret((good,))))
    with pytest.raises(TypeError, match="result players must be a tuple"):
        GameResult(cast(Any, [good]))
    with pytest.raises(TypeError, match="invalid element"):
        GameResult(cast(Any, (good, {"player_id": BOB})))
    with pytest.raises(ValueError, match="at least one"):
        GameResult(())
    with pytest.raises(ValueError, match="duplicate"):
        GameResult((PlayerResult(ALICE, 1, 1), PlayerResult(ALICE, -1, 2)))
    with pytest.raises(ValueError, match="conserved"):
        GameResult((PlayerResult(ALICE, 1, 1), PlayerResult(BOB, -2, 2)))


def test_apply_result_validates_state_events_order_and_recipients() -> None:
    _, state = new_game()
    ok = (GameEvent(1, "a", EventVisibility.PUBLIC), GameEvent(2, "b", EventVisibility.PUBLIC))
    assert ApplyResult(state, ok).events == ok
    with pytest.raises(TypeError, match="exact GameState"):
        ApplyResult(cast(GameState, object()))
    with pytest.raises(TypeError, match="events must be a tuple"):
        ApplyResult(state, cast(Any, TupleWithSecret(ok)))
    with pytest.raises(TypeError, match="events must be a tuple"):
        ApplyResult(state, cast(Any, list(ok)))
    with pytest.raises(ValueError, match="consecutive"):
        ApplyResult(state, (ok[0], GameEvent(3, "c", EventVisibility.PUBLIC)))
    with pytest.raises(ValueError, match="recipient must belong"):
        ApplyResult(state, (GameEvent(1, "a", EventVisibility.PRIVATE, UUID(int=99)),))


def test_event_subclass_carrying_hand_cannot_enter_apply_result() -> None:
    @dataclass(frozen=True, slots=True)
    class EventWithHand(GameEvent):
        hand: tuple[Card, ...] = ()

    _, state = new_game()
    leaked = EventWithHand(1, "a", EventVisibility.PUBLIC, hand=(Card.from_code("AS"),))
    assert "hand" in asdict(leaked)
    with pytest.raises(TypeError, match="exact GameEvent"):
        ApplyResult(state, (leaked,))


# ---- deck source rule ------------------------------------------------------


def test_production_deck_is_accepted_and_others_rejected() -> None:
    deck = Deck()
    assert require_production_deck(deck) is deck
    with pytest.raises(TestOnlyDeckError):
        require_production_deck(Deck.for_testing(Deck().deal(52)))
    with pytest.raises(ValueError, match="complete, undealt"):
        partial = Deck()
        partial.deal(1)
        require_production_deck(partial)
    for invalid in (None, [Card.from_code("AS")], "AS,KS", object()):
        with pytest.raises(TypeError, match="exact Deck"):
            require_production_deck(invalid)


def test_deck_subclass_lying_about_test_only_is_rejected() -> None:
    class LyingDeck(Deck):
        @property
        def is_test_only(self) -> bool:
            return False

    with pytest.raises(TypeError, match="exact Deck"):
        require_production_deck(LyingDeck())


def test_create_game_rejects_test_only_deck_and_bad_player_set() -> None:
    engine = StubEngine()
    players = (Player(ALICE, "Alice", 0), Player(BOB, "Bob", 1))
    with pytest.raises(TestOnlyDeckError):
        engine.create_game(
            GameConfig("stub", "1"), SESSION, players, Deck.for_testing(Deck().deal(52))
        )
    error = engine.create_game(GameConfig("stub", "1"), SESSION, players[:1], Deck())
    assert isinstance(error, GameError) and error.code == "bad_players"


# ---- engine contract -------------------------------------------------------


def test_validate_and_view_do_not_mutate_and_rejections_are_data() -> None:
    engine, state = new_game()
    before = repr(asdict(state))
    assert engine.validate_action(state, act(state, ALICE), StubPayload(1)).is_valid
    stale = replace(act(state, ALICE), state_version=9)
    assert engine.validate_action(state, stale, StubPayload(1)).error == GameError(
        "stale_state", "State is out of date"
    )
    assert engine.validate_action(state, act(state, BOB), StubPayload(1)).error is not None
    assert engine.validate_action(state, act(state, ALICE), StubPayload(0)).error is not None
    engine.get_player_view(state, ALICE)
    assert repr(asdict(state)) == before
    rejected = engine.apply_action(state, act(state, BOB), StubPayload(1))
    assert isinstance(rejected, GameError)


def test_apply_increments_version_orders_events_and_ends_game_with_conserved_result() -> None:
    engine, state = new_game()
    assert not engine.is_game_over(state)
    assert isinstance(engine.calculate_result(state), GameError)
    seqs: list[int] = []
    players = [ALICE, BOB]
    for step in range(3):
        outcome = engine.apply_action(state, act(state, players[step % 2]), StubPayload(1))
        assert isinstance(outcome, ApplyResult)
        assert outcome.state.public.state_version == state.public.state_version + 1
        seqs += [event.seq for event in outcome.events]
        state = outcome.state
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    assert engine.is_game_over(state)
    result = engine.calculate_result(state)
    assert isinstance(result, GameResult)
    assert sum(p.points_delta for p in result.players) == 0


def test_player_view_exposes_only_viewers_private_data() -> None:
    engine, state = new_game()
    view = engine.get_player_view(state, ALICE)
    assert isinstance(view, PlayerView)
    mine = {p.player_id: p.hand for p in state.private.players}
    assert view.private.hand == mine[ALICE]
    assert view.private.player_id == ALICE
    public_text = repr(asdict(view.public)) + repr(view.public)
    for other_card in (*mine[BOB], *state.private.remaining_cards):
        assert other_card.code not in public_text and repr(other_card) not in public_text
    unknown = engine.get_player_view(state, UUID(int=77))
    assert isinstance(unknown, GameError)


def test_modules_do_not_import_web_or_database_frameworks() -> None:
    root = Path(__file__).resolve().parents[2] / "app" / "games" / "core"
    forbidden = {"fastapi", "starlette", "sqlalchemy", "pydantic", "alembic"}
    for name in ("engine.py", "engine_types.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert not imported & forbidden
