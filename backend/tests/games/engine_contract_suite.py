"""Reusable GameEngine contract checks (P2-F). Every real engine must pass these.

check_engine_contract raises AssertionError on the first violation. It checks
contract semantics only (versions, events, view isolation, card conservation,
result conservation, test-only deck rejection); game rules stay in each engine's own tests.
The scenario supplies a legal script and one illegal action, since only the engine
knows its own legal moves.
"""

import copy
from collections.abc import Callable
from dataclasses import asdict, dataclass
from uuid import UUID

from app.games.core import (
    ApplyResult,
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
    max_steps: int = 200


def _snapshot(state: GameState) -> GameState:
    return copy.deepcopy(state)


def _hands(state: GameState) -> dict[UUID, tuple[object, ...]]:
    return {item.player_id: item.hand for item in state.private.players}


def _check_cards(state: GameState) -> None:
    cards = [card for item in state.private.players for card in item.hand]
    cards += list(state.private.remaining_cards)
    assert len(cards) == len(set(cards)), "a card appears more than once"
    assert len(cards) <= 52, "more than 52 cards in play"


def _check_views[PayloadT](engine: GameEngine[PayloadT], state: GameState) -> None:
    hands = _hands(state)
    for player in state.public.players:
        view = engine.get_player_view(state, player.id)
        assert isinstance(view, PlayerView), "member must receive a PlayerView"
        assert view.viewer_id == player.id and view.private.player_id == player.id
        assert view.private.hand == hands.get(player.id, ()), "view has the wrong hand"
        assert view.public == state.public, "view public data differs from state"
        text = repr(asdict(view.public)) + repr(view)
        others = [card for pid, hand in hands.items() if pid != player.id for card in hand] + list(
            state.private.remaining_cards
        )
        for card in others:
            assert repr(card) not in text, "another hand or the remaining deck leaked"
    outsider = engine.get_player_view(state, UUID(int=2**100))
    assert isinstance(outsider, GameError), "a non-member must not receive a view"


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

    # Rejections are data, never change the state, and not over yet.
    assert not engine.is_game_over(state), "a new game cannot already be over"
    assert isinstance(engine.calculate_result(state), GameError), "result before game over"
    before = _snapshot(state)
    action, payload = scenario.illegal(state)
    assert engine.validate_action(state, action, payload).error is not None, (
        "illegal action accepted"
    )
    assert isinstance(engine.apply_action(state, action, payload), GameError), (
        "illegal action applied"
    )
    action, payload = scenario.stale(state)
    assert engine.validate_action(state, action, payload).error is not None, (
        "stale version accepted"
    )
    assert isinstance(engine.apply_action(state, action, payload), GameError), (
        "stale version applied"
    )
    assert state == before, "a rejected action changed the state"

    # Legal script: version + 1, consecutive events, identity preserved.
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

    # Game over: result covers exactly the players and conserves points.
    assert engine.is_game_over(state), "script finished but the game is not over"
    result = engine.calculate_result(state)
    assert isinstance(result, GameResult), "no result after game over"
    assert {p.player_id for p in result.players} == {p.id for p in state.public.players}, (
        "result must cover exactly the players"
    )
    assert sum(p.points_delta for p in result.players) == 0
    # No further actions once over.
    if scenario.players:
        late_action, late_payload = scenario.illegal(state)
        assert engine.validate_action(state, late_action, late_payload).error is not None
