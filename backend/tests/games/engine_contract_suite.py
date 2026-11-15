"""Reusable GameEngine contract checks (P2-F, extended in P3-00). Every real engine must pass.

check_engine_contract raises AssertionError on the first violation. It checks
contract semantics only: test-only deck rejection, version and event ordering,
card conservation, view isolation, result conservation, determinism, safe error
messages and rejection of actions after the game is over. Game rules stay in each
engine's own tests. The scenario supplies a legal script plus an illegal, a stale and
an after-game-over action, since only the engine knows its own legal moves.
"""

import copy
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from uuid import UUID

from app.games.core import (
    ApplyResult,
    Card,
    Deck,
    GameAction,
    GameConfig,
    GameEngine,
    GameError,
    GameResult,
    GameState,
    Player,
    PlayerView,
    TestOnlyDeckError,
)


@dataclass(frozen=True)
class ContractScenario[PayloadT]:
    config: GameConfig
    session_id: UUID
    players: tuple[Player, ...]
    # Next legal (action, payload) for a state, or None when the script has no more moves.
    next_legal: Callable[[GameState], tuple[GameAction, PayloadT] | None]
    # One action that is illegal in the given (non-final) state, e.g. wrong turn.
    illegal: Callable[[GameState], tuple[GameAction, PayloadT]]
    stale: Callable[[GameState], tuple[GameAction, PayloadT]]
    # A well-formed action for the finished game (current version, plausible actor).
    after_over: Callable[[GameState], tuple[GameAction, PayloadT]]
    max_steps: int = 200


def _snapshot(state: GameState) -> GameState:
    return copy.deepcopy(state)


def _hands(state: GameState) -> dict[UUID, tuple[Card, ...]]:
    return {item.player_id: item.hand for item in state.private.players}


def _secret_cards(state: GameState) -> list[Card]:
    cards = [card for item in state.private.players for card in item.hand]
    return cards + list(state.private.remaining_cards)


def _check_cards(state: GameState) -> None:
    cards = _secret_cards(state)
    assert len(cards) == len(set(cards)), "a card appears more than once"
    assert len(cards) <= 52, "more than 52 cards in play"


def _assert_safe(error: object, state: GameState, what: str) -> None:
    """GameError text must never reveal a hidden card (hands or the undealt deck)."""
    assert isinstance(error, GameError), f"{what} must be a GameError"
    text = f"{error.code} {error.message}"
    for card in _secret_cards(state):
        assert repr(card) not in text, f"{what} reveals a hidden card"
        pattern = rf"(?<![A-Za-z0-9]){re.escape(card.code)}(?![A-Za-z0-9])"
        assert re.search(pattern, text) is None, f"{what} reveals a hidden card code"


def _check_views[PayloadT](engine: GameEngine[PayloadT], state: GameState) -> None:
    hands = _hands(state)
    for player in state.public.players:
        view = engine.get_player_view(state, player.id)
        assert isinstance(view, PlayerView), "member must receive a PlayerView"
        assert view.viewer_id == player.id and view.private.player_id == player.id
        assert view.private.hand == hands.get(player.id, ()), "view has the wrong hand"
        assert view.public == state.public, "view public data differs from state"
        assert view.extension == state.extension, "view extension differs from state"
        assert engine.get_player_view(state, player.id) == view, "get_player_view is not repeatable"
        text = repr(asdict(view.public)) + repr(view)
        others = [card for pid, hand in hands.items() if pid != player.id for card in hand] + list(
            state.private.remaining_cards
        )
        for card in others:
            assert repr(card) not in text, "another hand or the remaining deck leaked"
    outsider = engine.get_player_view(state, UUID(int=2**100))
    assert isinstance(outsider, GameError), "a non-member must not receive a view"
    _assert_safe(outsider, state, "non-member view error")


def _check_rejection[PayloadT](
    engine: GameEngine[PayloadT],
    state: GameState,
    action: GameAction,
    payload: PayloadT,
    what: str,
) -> None:
    before = _snapshot(state)
    validation = engine.validate_action(state, action, payload)
    assert validation.error is not None, f"{what} accepted by validate_action"
    _assert_safe(validation.error, state, f"{what} validation error")
    applied = engine.apply_action(state, action, payload)
    assert isinstance(applied, GameError), f"{what} applied by apply_action"
    _assert_safe(applied, state, f"{what} apply error")
    assert engine.validate_action(state, action, payload) == validation, (
        f"{what} validation is not repeatable"
    )
    assert engine.apply_action(state, action, payload) == applied, (
        f"{what} rejection is not repeatable"
    )
    assert state == before, f"{what} changed the state"


def check_engine_contract[PayloadT](
    engine: GameEngine[PayloadT], scenario: ContractScenario[PayloadT]
) -> None:
    # create_game: production deck accepted, test-only deck rejected.
    try:
        engine.create_game(
            scenario.config,
            scenario.session_id,
            scenario.players,
            Deck.for_testing(Deck().deal(52)),
        )
    except TestOnlyDeckError:
        pass
    else:
        raise AssertionError("engine accepted a test-only deck")
    created = engine.create_game(scenario.config, scenario.session_id, scenario.players, Deck())
    assert isinstance(created, GameState), "create_game failed with a production deck"
    state = created
    assert state.session_id == scenario.session_id
    assert state.game_type == scenario.config.game_type
    assert state.rules_version == scenario.config.rules_version
    assert tuple(p.id for p in state.public.players) == tuple(p.id for p in scenario.players)
    _check_cards(state)
    _check_views(engine, state)

    # Rejections are repeatable data, reveal nothing, never change the state.
    assert not engine.is_game_over(state), "a new game cannot already be over"
    early = engine.calculate_result(state)
    assert isinstance(early, GameError), "result before game over"
    _assert_safe(early, state, "early result error")
    action, payload = scenario.illegal(state)
    _check_rejection(engine, state, action, payload, "illegal action")
    action, payload = scenario.stale(state)
    _check_rejection(engine, state, action, payload, "stale version")

    # Legal script: version + 1, increasing events, identity preserved, deterministic.
    last_seq = -1
    for _ in range(scenario.max_steps):
        step = scenario.next_legal(state)
        if step is None:
            break
        action, payload = step
        before = _snapshot(state)
        assert engine.validate_action(state, action, payload).is_valid
        assert state == before, "validate_action changed the state"
        outcome = engine.apply_action(state, action, payload)
        assert isinstance(outcome, ApplyResult), "a legal action was rejected"
        assert state == before, "apply_action mutated its input"
        assert engine.apply_action(state, action, payload) == outcome, (
            "apply_action is not deterministic"
        )
        new = outcome.state
        assert new.public.state_version == state.public.state_version + 1, (
            "version must increase by exactly 1"
        )
        assert (new.session_id, new.game_type, new.rules_version) == (
            state.session_id,
            state.game_type,
            state.rules_version,
        ), "session identity or rules version changed"
        assert [p.id for p in new.public.players] == [p.id for p in state.public.players]
        for event in outcome.events:
            assert event.seq > last_seq, "event seq must keep increasing across steps"
            last_seq = event.seq
        _check_cards(new)
        _check_views(engine, new)
        state = new
    else:
        raise AssertionError("script did not finish within max_steps")

    # Game over: result covers exactly the players, conserves points, is repeatable.
    assert engine.is_game_over(state), "script finished but the game is not over"
    result = engine.calculate_result(state)
    assert isinstance(result, GameResult), "no result after game over"
    assert engine.calculate_result(state) == result, "calculate_result is not repeatable"
    assert {p.player_id for p in result.players} == {p.id for p in state.public.players}, (
        "result must cover exactly the players"
    )
    assert sum(p.points_delta for p in result.players) == 0
    # A well-formed action after the game is over must be rejected.
    late_action, late_payload = scenario.after_over(state)
    _check_rejection(engine, state, late_action, late_payload, "action after game over")
