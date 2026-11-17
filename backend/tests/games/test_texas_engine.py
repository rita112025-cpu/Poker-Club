"""P3-02: Texas street machine and fold/check/call engine.

Expected flows are written out by hand against a fixed deck (AS KS QS JS 10S 9S ...), not
derived with the code under test. Rules values are TEST FIXTURES. Not applicable: bet,
raise and over-all-in (P3-03, asserted as NOT_SUPPORTED_YET), side pots and settlement
(P3-04), registry integration and the full contract incl. results (P3-05).
"""

import random
from dataclasses import replace
from typing import Any, cast
from uuid import UUID

import pytest
from engine_contract_suite import ContractScenario, check_engine_contract

from app.games.core import (
    Card,
    Deck,
    EventVisibility,
    GameAction,
    GameConfig,
    GameEngine,
    GameError,
    GameResult,
    GameState,
    GameStatus,
    Player,
    PlayerView,
    TestOnlyDeckError,
    events_for_viewer,
    project_player_view,
)
from app.games.texas_holdem import (
    ActionTaken,
    HandEnd,
    HandEnded,
    Street,
    StreetDealt,
    TexasEngine,
    TexasPayload,
    TexasPublic,
    TexasRules,
    legal_actions,
)

RULES = TexasRules("test-1", 5, 10, False)  # fixture values only
RULES_BURN = TexasRules("test-1", 5, 10, True)
SESSION = UUID(int=700)
CONFIG = GameConfig("texas_holdem", "test-1")
NONE = TexasPayload()


def pid(seat: int) -> UUID:
    return UUID(int=100 + seat)


def fixed_deck() -> Deck:
    codes = [
        rank + suit
        for suit in "SHDC"
        for rank in ("A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2")
    ]
    return Deck.for_testing(Card.from_code(code) for code in codes)


def cards(*codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes)


def new_hand(
    stacks: dict[int, int],
    button: int | None = None,
    rules: TexasRules = RULES,
    deck: Deck | None = None,
) -> tuple[TexasEngine, GameState]:
    engine = TexasEngine(rules)
    players = tuple(Player(pid(seat), f"p{seat}", seat, stack) for seat, stack in stacks.items())
    config = GameConfig("texas_holdem", rules.version)
    created = engine.create_game_for_testing(config, SESSION, players, deck or fixed_deck(), button)
    assert isinstance(created, GameState), created
    return engine, created


def ext(state: GameState) -> TexasPublic:
    assert isinstance(state.extension, TexasPublic)
    return state.extension


def turn_seat(state: GameState) -> int:
    assert state.public.turn is not None
    return next(s.seat for s in ext(state).seats if s.player_id == state.public.turn.player_id)


def act(
    engine: TexasEngine, state: GameState, kind: str, payload: TexasPayload = NONE
) -> tuple[GameState, tuple[Any, ...]]:
    assert state.public.turn is not None
    action = GameAction(
        state.public.turn.player_id,
        UUID(int=5000 + state.public.state_version),
        state.public.state_version,
        kind,
    )
    result = engine.apply_action(state, action, payload)
    assert not isinstance(result, GameError), result
    return result.state, tuple(e.payload for e in result.events)


def pick_move(generator: random.Random, legal: Any) -> tuple[str, TexasPayload]:
    options = [k for k in legal.kinds if k != "fold"] or ["fold"]
    kind = "fold" if generator.random() < 0.12 else generator.choice(options)
    if kind in ("bet", "raise"):
        amount = generator.choice(
            [legal.min_to, legal.max_to, generator.randint(legal.min_to, legal.max_to)]
        )
        return kind, TexasPayload(amount)
    return kind, NONE


def error_of(
    engine: TexasEngine,
    state: GameState,
    kind: str,
    payload: TexasPayload = NONE,
    *,
    player: UUID | None = None,
    version: int | None = None,
) -> GameError:
    turn = state.public.turn
    action = GameAction(
        player or (turn.player_id if turn else pid(0)),
        UUID(int=9000),
        state.public.state_version if version is None else version,
        kind,
    )
    before = state
    validation = engine.validate_action(state, action, payload)
    applied = engine.apply_action(state, action, payload)
    assert validation.error is not None and isinstance(applied, GameError)
    assert validation.error == applied
    assert state == before  # a rejection never changes the state
    return applied


def test_engine_satisfies_the_protocol_statically() -> None:
    engine: GameEngine[TexasPayload] = TexasEngine(RULES)
    assert engine is not None


# ---- legal actions (hand-written table) ------------------------------------------------


def test_legal_actions_in_representative_spots() -> None:
    # seats 0,1,2 button 0: SB seat 1 posts 5, BB seat 2 posts 10, seat 0 acts first.
    _, state = new_hand({0: 100, 1: 100, 2: 100}, 0)
    assert turn_seat(state) == 0
    legal = legal_actions(state)
    assert legal is not None and legal.kinds == ("fold", "call", "all_in", "raise")
    assert legal.to_call == 10 and (legal.min_to, legal.max_to) == (20, 100)
    # a short stack facing 10 may call all-in
    _, short = new_hand({0: 8, 1: 100, 2: 100}, 0)
    legal = legal_actions(short)
    assert legal is not None and legal.kinds == ("fold", "call", "all_in") and legal.to_call == 10
    # exactly covering the call: call and all-in are the same move
    _, exact = new_hand({0: 10, 1: 100, 2: 100}, 0)
    legal = legal_actions(exact)
    assert legal is not None and legal.kinds == ("fold", "call", "all_in")


def test_big_blind_keeps_its_option_and_postflop_spots_allow_check_or_fold() -> None:
    engine, state = new_hand({0: 100, 1: 100, 2: 100}, 0)
    state, _ = act(engine, state, "call")  # seat 0
    state, _ = act(engine, state, "call")  # seat 1 (small blind completes)
    assert turn_seat(state) == 2 and ext(state).street is Street.PRE_FLOP
    legal = legal_actions(state)  # the option: check, or raise to at least 20
    assert legal is not None and legal.kinds == ("fold", "check", "all_in", "raise")
    assert legal.to_call == 0 and (legal.min_to, legal.max_to) == (20, 100)
    state, _ = act(engine, state, "check")
    assert ext(state).street is Street.FLOP and turn_seat(state) == 1
    legal = legal_actions(state)  # nothing bet yet: check, or bet at least the big blind
    assert legal is not None and legal.kinds == ("fold", "check", "all_in", "bet")
    assert (legal.min_to, legal.max_to) == (10, 90)


def test_no_legal_actions_once_the_hand_is_over() -> None:
    engine, state = new_hand({0: 100, 1: 100}, 0)
    state, _ = act(engine, state, "fold")
    assert state.public.status is GameStatus.FINISHED and legal_actions(state) is None


# ---- rejections are data -------------------------------------------------------------


def test_rejections_use_stable_codes_and_never_change_the_state() -> None:
    engine, state = new_hand({0: 100, 1: 100, 2: 100}, 0)
    assert error_of(engine, state, "check").code == "illegal_action"  # facing 10
    assert error_of(engine, state, "dance").code == "unknown_action"
    assert error_of(engine, state, "fold", TexasPayload(5)).code == "bad_payload"
    assert error_of(engine, state, "call", player=pid(1)).code == "not_your_turn"
    assert error_of(engine, state, "call", version=7).code == "stale_state"
    assert (
        error_of(engine, state, "bet", TexasPayload(40)).code == "illegal_action"
    )  # a bet is open
    assert error_of(engine, state, "raise").code == "bad_payload"  # no amount
    assert error_of(engine, state, "raise", TexasPayload(19)).code == "bad_amount"  # below 20
    assert error_of(engine, state, "raise", TexasPayload(101)).code == "bad_amount"  # above stack
    assert error_of(engine, state, "raise", TexasPayload(0)).code == "bad_amount"
    state, _ = act(engine, state, "call")
    state, _ = act(engine, state, "call")
    state, _ = act(engine, state, "check")  # flop, seat 1 to act with nothing owed
    assert error_of(engine, state, "call").code == "illegal_action"
    assert error_of(engine, state, "raise", TexasPayload(40)).code == "illegal_action"  # no bet yet
    assert error_of(engine, state, "bet").code == "bad_payload"
    assert error_of(engine, state, "bet", TexasPayload(9)).code == "bad_amount"  # below the blind
    assert error_of(engine, state, "bet", TexasPayload(91)).code == "bad_amount"  # above the stack
    for _ in range(3):  # checks to the river, then the showdown
        state, _ = act(engine, state, "check")
        state, _ = act(engine, state, "check")
        state, _ = act(engine, state, "check")
    assert state.public.status is GameStatus.FINISHED
    assert error_of(engine, state, "check").code == "game_over"


def test_error_messages_never_name_cards() -> None:
    engine, state = new_hand({0: 100, 1: 100, 2: 100}, 0)
    text = " ".join(
        error_of(engine, state, kind, payload).message
        for kind, payload in (("check", NONE), ("dance", NONE), ("bet", TexasPayload(5)))
    )
    for card in cards("AS", "KS", "QS", "JS", "10S", "9S"):
        assert card.code not in text


def test_payload_and_input_types_are_enforced() -> None:
    engine, state = new_hand({0: 100, 1: 100}, 0)
    action = GameAction(state.public.turn.player_id, UUID(int=1), 0, "call")  # type: ignore[union-attr]
    with pytest.raises(TypeError):
        engine.validate_action(state, action, cast(TexasPayload, {"amount": None}))
    with pytest.raises(TypeError):
        engine.validate_action(cast(GameState, None), action, NONE)
    for bad in (-1, True, 1.5, "5"):
        with pytest.raises((TypeError, ValueError)):
            TexasPayload(cast(int, bad))


# ---- hand-written flows (fixed deck: hole cards use the first 2n cards) -------------------


def test_heads_up_check_down_with_known_board_and_events() -> None:
    # seats 0,1 button 0: seat 0 is the small blind and acts first; the big blind is seat 1.
    engine, state = new_hand({0: 100, 1: 100}, 0)
    assert turn_seat(state) == 0
    state, events = act(engine, state, "call")
    assert events == (ActionTaken(0, "call", 5, 10),) and turn_seat(state) == 1
    state, events = act(engine, state, "check")  # the big blind's option
    assert events == (
        ActionTaken(1, "check", 0, 10),
        StreetDealt(Street.FLOP, cards("10S", "9S", "8S")),
    )
    assert ext(state).street is Street.FLOP and turn_seat(state) == 1  # big blind first
    state, _ = act(engine, state, "check")
    state, events = act(engine, state, "check")
    assert events[-1] == StreetDealt(Street.TURN, cards("7S"))
    state, _ = act(engine, state, "check")
    state, events = act(engine, state, "check")
    assert events[-1] == StreetDealt(Street.RIVER, cards("6S"))
    state, _ = act(engine, state, "check")
    state, events = act(engine, state, "check")
    assert events[-1] == HandEnded(HandEnd.SHOWDOWN)
    table = ext(state)
    assert table.street is Street.SHOWDOWN and table.ended is HandEnd.SHOWDOWN
    assert table.board == cards("10S", "9S", "8S", "7S", "6S") and table.pot == 20
    assert state.public.status is GameStatus.FINISHED and state.public.turn is None
    assert state.public.state_version == 8  # one per action


def test_burn_cards_are_skipped_before_each_street() -> None:
    engine, state = new_hand({0: 100, 1: 100}, 0, RULES_BURN)
    for _ in range(8):
        state, _ = act(engine, state, "call" if state.public.state_version == 0 else "check")
    # hole cards AS KS QS JS; burn 10S, flop 9S 8S 7S; burn 6S, turn 5S; burn 4S, river 3S
    assert ext(state).board == cards("9S", "8S", "7S", "5S", "3S")
    assert state.public.status is GameStatus.FINISHED
    left = state.private.remaining_cards
    assert left[0] == Card.from_code("2S") and len(left) == 52 - 4 - 8


def test_three_handed_call_through_and_big_blind_option() -> None:
    engine, state = new_hand({0: 100, 1: 100, 2: 100}, 0)
    state, _ = act(engine, state, "call")  # seat 0
    state, events = act(engine, state, "call")  # seat 1 completes the small blind
    assert (
        events == (ActionTaken(1, "call", 5, 10),) and turn_seat(state) == 2
    )  # option, no street yet
    state, events = act(engine, state, "check")
    assert events[-1] == StreetDealt(Street.FLOP, cards("8S", "7S", "6S"))  # six hole cards
    assert ext(state).pot == 30 and [turn_seat(state)] == [1]  # first live seat left of the button


def test_everyone_folds_to_the_big_blind() -> None:
    engine, state = new_hand({0: 100, 1: 100, 2: 100}, 0)
    state, _ = act(engine, state, "fold")
    state, events = act(engine, state, "fold")
    assert events[-1] == HandEnded(HandEnd.LAST_STANDING)
    table = ext(state)
    assert table.ended is HandEnd.LAST_STANDING and table.street is Street.PRE_FLOP
    assert table.board == () and table.pot == 15
    assert state.public.status is GameStatus.FINISHED and state.public.turn is None


def test_fold_on_the_flop_ends_the_hand_without_a_showdown() -> None:
    engine, state = new_hand({0: 100, 1: 100}, 0)
    state, _ = act(engine, state, "call")
    state, _ = act(engine, state, "check")
    state, events = act(engine, state, "fold")  # big blind folds first on the flop
    assert events == (ActionTaken(1, "fold", 0, 0), HandEnded(HandEnd.LAST_STANDING))
    table = ext(state)
    assert (
        table.street is Street.FLOP
        and len(table.board) == 3
        and table.ended is HandEnd.LAST_STANDING
    )


def test_short_all_in_call_keeps_the_hand_going_for_the_others() -> None:
    engine, state = new_hand({0: 8, 1: 100, 2: 100}, 0)
    state, events = act(engine, state, "all_in")  # seat 0 pays only 8 of the 10
    assert events == (ActionTaken(0, "all_in", 8, 8),) and turn_seat(state) == 1
    seat0 = next(s for s in ext(state).seats if s.seat == 0)
    assert seat0.all_in and seat0.stack == 0 and seat0.committed == 8
    state, _ = act(engine, state, "call")
    state, _ = act(engine, state, "check")
    table = ext(state)
    assert table.street is Street.FLOP and table.pot == 28 and turn_seat(state) == 1
    for _ in range(6):  # seats 1 and 2 check down; seat 0 is all-in and skipped
        state, _ = act(engine, state, "check")
    assert ext(state).ended is HandEnd.SHOWDOWN and ext(state).pot == 28


def test_everyone_all_in_runs_the_board_out_without_betting() -> None:
    engine, state = new_hand({0: 1, 1: 2, 2: 3}, 0)  # blinds 5/10 swallow the small stacks
    assert turn_seat(state) == 0
    state, events = act(engine, state, "all_in")
    assert [type(e) for e in events] == [
        ActionTaken,
        StreetDealt,
        StreetDealt,
        StreetDealt,
        HandEnded,
    ]
    assert [e.street for e in events if isinstance(e, StreetDealt)] == [
        Street.FLOP,
        Street.TURN,
        Street.RIVER,
    ]
    table = ext(state)
    assert table.ended is HandEnd.SHOWDOWN and len(table.board) == 5 and table.pot == 6
    assert state.public.turn is None


def test_a_hand_where_nobody_can_act_from_the_start_is_dealt_out_at_creation() -> None:
    _, state = new_hand({0: 4, 1: 6}, 0, TexasRules("test-1", 10, 20, False))
    table = ext(state)
    assert state.public.status is GameStatus.FINISHED and state.public.turn is None
    assert table.ended is HandEnd.SHOWDOWN and len(table.board) == 5 and table.pot == 10
    assert state.public.state_version == 1  # the run-out counts as one step


def test_a_single_active_player_against_all_in_opponents_gets_no_betting() -> None:
    engine, state = new_hand({0: 100, 1: 2, 2: 3}, 0)  # SB and BB are all-in for 2 and 3
    assert turn_seat(state) == 0
    state, events = act(engine, state, "call")  # pays 3
    assert [type(e) for e in events] == [
        ActionTaken,
        StreetDealt,
        StreetDealt,
        StreetDealt,
        HandEnded,
    ]
    assert ext(state).pot == 8 and state.public.status is GameStatus.FINISHED


def test_small_blind_folds_heads_up() -> None:
    engine, state = new_hand({0: 100, 1: 100}, 0)
    state, events = act(engine, state, "fold")
    assert events[-1] == HandEnded(HandEnd.LAST_STANDING) and ext(state).pot == 15


def test_rotating_the_button_changes_the_first_actor() -> None:
    _, one = new_hand({0: 100, 1: 100, 2: 100, 3: 100}, 1)  # SB 2, BB 3, first to act 0
    assert turn_seat(one) == 0
    _, two = new_hand({0: 100, 1: 100, 2: 100, 3: 100}, 3)  # SB 0, BB 1, first to act 2
    assert turn_seat(two) == 2 and ext(two).small_blind_seat == 0


# ---- events, views ---------------------------------------------------------------------


def test_event_sequence_numbers_continue_across_actions() -> None:
    engine, state = new_hand({0: 100, 1: 100}, 0)
    seen: list[int] = []
    while state.public.status is GameStatus.IN_PROGRESS:
        action = GameAction(
            state.public.turn.player_id,  # type: ignore[union-attr]
            UUID(int=1),
            state.public.state_version,
            "call" if state.public.state_version == 0 else "check",
        )
        result = engine.apply_action(state, action, NONE)
        assert not isinstance(result, GameError)
        seen += [e.seq for e in result.events]
        assert all(e.visibility is EventVisibility.PUBLIC for e in result.events)
        assert ext(result.state).event_seq == seen[-1] + 1
        state = result.state
    assert seen == list(range(len(seen)))


def test_views_show_the_board_but_never_hole_cards_or_the_deck() -> None:
    engine, state = new_hand({0: 100, 1: 100, 2: 100}, 0)
    for kind in ("call", "call", "check"):
        state, _ = act(engine, state, kind)
    for player in state.public.players:
        view = engine.get_player_view(state, player.id)
        assert isinstance(view, PlayerView) and isinstance(view.extension, TexasPublic)
        assert view.extension.board == cards("8S", "7S", "6S")
        mine = {p.player_id: p.hand for p in state.private.players}[player.id]
        assert view.private.hand == mine
        shown = repr(view) + repr(view.extension)
        for other in state.private.players:
            if other.player_id != player.id:
                assert all(repr(card) not in shown for card in other.hand)
        assert all(repr(card) not in shown for card in state.private.remaining_cards)
    outsider = engine.get_player_view(state, UUID(int=5))
    assert isinstance(outsider, GameError)


def test_every_street_event_is_visible_to_every_viewer() -> None:
    engine, state = new_hand({0: 100, 1: 100}, 0)
    state, _ = act(engine, state, "call")
    result = engine.apply_action(state, GameAction(pid(1), UUID(int=2), 1, "check"), NONE)
    assert not isinstance(result, GameError)
    for seat in (0, 1):
        assert events_for_viewer(result.events, pid(seat)) == result.events


# ---- creation and results ----------------------------------------------------------


def test_create_game_checks_configuration_and_the_production_deck_gate() -> None:
    engine = TexasEngine(RULES)
    players = tuple(Player(pid(s), f"p{s}", s, 100) for s in (0, 1, 2))
    wrong = engine.create_game(GameConfig("big_two", "test-1"), SESSION, players, Deck())
    assert isinstance(wrong, GameError) and wrong.code == "config_mismatch"
    old = engine.create_game(GameConfig("texas_holdem", "other"), SESSION, players, Deck())
    assert isinstance(old, GameError) and old.code == "config_mismatch"
    with pytest.raises(TestOnlyDeckError):
        engine.create_game(CONFIG, SESSION, players, fixed_deck())
    created = engine.create_game(CONFIG, SESSION, players, Deck())
    assert isinstance(created, GameState) and created.public.state_version == 0
    assert isinstance(engine.create_game(CONFIG, SESSION, players[:1], Deck()), GameError)


def test_result_is_unavailable_until_the_hand_is_over_and_then_settles() -> None:
    engine, state = new_hand({0: 100, 1: 100}, 0)
    early = engine.calculate_result(state)
    assert isinstance(early, GameError) and early.code == "not_finished"
    state, _ = act(engine, state, "fold")  # the small blind folds: the big blind wins 5
    assert engine.is_game_over(state)
    late = engine.calculate_result(state)
    assert isinstance(late, GameResult)
    by_player = {p.player_id: (p.points_delta, p.rank) for p in late.players}
    assert by_player == {pid(1): (5, 1), pid(0): (-5, 2)}


# ---- shared contract suite ----------------------------------------------------------


def test_the_shared_contract_suite_passes_for_the_fold_check_call_engine() -> None:
    engine = TexasEngine(RULES)
    players = tuple(Player(pid(s), f"p{s}", s, 100) for s in (0, 1, 2))

    def next_legal(state: GameState) -> tuple[GameAction, TexasPayload] | None:
        legal = legal_actions(state)
        if legal is None or state.public.turn is None:
            return None
        kind = "check" if "check" in legal.kinds else "call"
        version = state.public.state_version
        return GameAction(state.public.turn.player_id, UUID(int=40 + version), version, kind), NONE

    def illegal(state: GameState) -> tuple[GameAction, TexasPayload]:
        assert state.public.turn is not None
        version = state.public.state_version
        return GameAction(state.public.turn.player_id, UUID(int=60), version, "bet"), TexasPayload(
            9
        )

    def stale(state: GameState) -> tuple[GameAction, TexasPayload]:
        assert state.public.turn is not None
        version = state.public.state_version + 5
        return GameAction(state.public.turn.player_id, UUID(int=61), version, "call"), NONE

    def after_over(state: GameState) -> tuple[GameAction, TexasPayload]:
        return GameAction(pid(0), UUID(int=62), state.public.state_version, "check"), NONE

    scenario = ContractScenario(
        CONFIG,
        SESSION,
        players,
        next_legal,
        illegal,
        stale,
        after_over,
        revealed=shown_cards,
        results_supported=True,
    )
    check_engine_contract(engine, scenario)


# ---- random playouts: invariants after every step ----------------------------------------


def shown_cards(state: GameState) -> frozenset[Card]:
    """Cards the engine has made public: the board and any hands shown at a showdown."""
    table = ext(state)
    return frozenset(table.board) | frozenset(c for hand in table.showdown for c in hand.cards)


def check_invariants(state: GameState, previous: GameState | None, total: int) -> None:
    table = ext(state)
    assert sum(s.stack for s in table.seats) + table.pot == total  # points are conserved
    in_play = [c for p in state.private.players for c in p.hand]
    in_play += list(state.private.remaining_cards) + list(table.board)
    assert len(in_play) == len(set(in_play)) <= 52  # no card appears twice
    assert all(s.all_in == (s.stack == 0) for s in table.seats)
    assert (
        len(table.board)
        == {"pre_flop": 0, "flop": 3, "turn": 4, "river": 5, "showdown": 5}[table.street.value]
    )
    if previous is not None:
        assert state.public.state_version == previous.public.state_version + 1
        assert table.event_seq > ext(previous).event_seq
        assert set(ext(previous).board) <= set(table.board)  # the board only grows
        if ext(previous).street is table.street:  # within a street both only grow
            assert table.current_bet >= ext(previous).current_bet
            assert table.min_raise >= ext(previous).min_raise
        assert all(
            a.committed >= b.committed
            for a, b in zip(table.seats, ext(previous).seats, strict=True)
        )
    if state.public.status is GameStatus.IN_PROGRESS:
        holder = turn_seat(state)
        seat = next(s for s in table.seats if s.seat == holder)
        assert not seat.folded and not seat.all_in


def test_random_playouts_always_finish_with_valid_states() -> None:
    generator = random.Random(20261116)
    endings: set[HandEnd] = set()
    runouts = short_calls = raises = 0
    for _ in range(1500):
        count = generator.randint(2, 9)
        seats = sorted(generator.sample(range(12), count))
        stacks = {s: generator.choice([1, 2, 3, 5, 8, 10, 12, 30, 100, 400]) for s in seats}
        rules = RULES_BURN if generator.random() < 0.5 else RULES
        engine, state = new_hand(stacks, generator.choice(seats), rules, deck=fixed_deck())
        total = sum(stacks.values())
        check_invariants(state, None, total)
        for _step in range(400):
            if state.public.status is GameStatus.FINISHED:
                break
            legal = legal_actions(state)
            assert legal is not None
            kind, move = pick_move(generator, legal)
            previous = state
            assert state.public.turn is not None
            action = GameAction(
                state.public.turn.player_id,
                UUID(int=1),
                state.public.state_version,
                kind,
            )
            repeat = engine.apply_action(state, action, move)
            assert repeat == engine.apply_action(state, action, move)  # deterministic
            assert not isinstance(repeat, GameError), repeat
            state = repeat.state
            check_invariants(state, previous, total)
            kinds = [type(e.payload) for e in repeat.events]
            runouts += kinds.count(StreetDealt) >= 2
            short_calls += kind == "all_in"
            raises += kind in ("bet", "raise")
        else:
            raise AssertionError("a hand did not finish")
        endings.add(ext(state).ended)
    assert endings == {HandEnd.LAST_STANDING, HandEnd.SHOWDOWN}
    assert runouts > 50 and short_calls > 50 and raises > 500  # the paths were exercised


def test_rejected_actions_in_random_states_never_change_them() -> None:
    generator = random.Random(7)
    for _ in range(300):
        count = generator.randint(2, 6)
        stacks = {s: generator.choice([3, 10, 100]) for s in range(count)}
        engine, state = new_hand(stacks, 0)
        while state.public.status is GameStatus.IN_PROGRESS:
            for kind in ("bet", "raise", "check", "call", "all_in", "x"):
                legal = legal_actions(state)
                assert legal is not None
                if kind in legal.kinds:
                    continue
                before = state
                action = GameAction(
                    state.public.turn.player_id,  # type: ignore[union-attr]
                    UUID(int=1),
                    state.public.state_version,
                    kind,
                )
                assert isinstance(engine.apply_action(state, action, NONE), GameError)
                assert state == before
            kind, move = pick_move(generator, legal_actions(state))
            state, _ = act(engine, state, kind, move)


def test_projection_of_every_state_in_a_hand_is_valid_for_every_player() -> None:
    engine, state = new_hand({0: 100, 1: 100, 2: 100}, 0)
    while state.public.status is GameStatus.IN_PROGRESS:
        for player in state.public.players:
            view = project_player_view(state, player.id)
            assert isinstance(view, PlayerView)
        legal = legal_actions(state)
        assert legal is not None
        state, _ = act(engine, state, "check" if "check" in legal.kinds else "call")
    replace_ok = replace(state, extension=state.extension)
    assert replace_ok == state


# ---- P3-02-0: the table data must agree with the core public data ---------------------------


def test_extension_must_match_the_players_and_their_chips() -> None:
    _, state = new_hand({0: 100, 1: 100, 2: 100}, 0)
    table = ext(state)
    other = replace(
        table, seats=tuple(replace(s, player_id=UUID(int=900 + s.seat)) for s in table.seats)
    )
    with pytest.raises(ValueError, match="seats must match the players"):
        replace(state, extension=other)
    rich = replace(table, seats=tuple(replace(s, stack=s.stack + 10**6) for s in table.seats))
    with pytest.raises(ValueError, match="add up"):
        replace(state, extension=rich)  # pot still matches, chips do not
    shifted = replace(
        table,
        seats=tuple(replace(s, seat=s.seat + 1) for s in table.seats),
        button_seat=1,
        small_blind_seat=2,
        big_blind_seat=3,
    )
    with pytest.raises(ValueError, match="seats must match the players"):
        replace(state, extension=shifted)


def test_turn_and_status_must_agree_with_the_table_data() -> None:
    engine, state = new_hand({0: 100, 1: 100, 2: 100}, 0)
    table = ext(state)
    folded = tuple(replace(s, folded=True) if s.seat == 0 else s for s in table.seats)
    with pytest.raises(ValueError, match="can act"):
        replace(state, extension=replace(table, seats=folded))  # seat 0 holds the turn
    with pytest.raises(ValueError, match="finished"):
        replace(state, public=replace(state.public, status=GameStatus.FINISHED, turn=None))
    done, _ = act(engine, state, "fold")
    done, _ = act(engine, done, "fold")
    assert done.public.status is GameStatus.FINISHED
    with pytest.raises(ValueError, match="finished"):
        replace(done, public=replace(done.public, status=GameStatus.IN_PROGRESS))
    with pytest.raises(ValueError, match="no turn"):
        replace(done, public=replace(done.public, turn=state.public.turn))


def test_projection_revalidates_a_table_altered_after_construction() -> None:
    _, state = new_hand({0: 100, 1: 100}, 0)
    seats = ext(state).seats
    object.__setattr__(
        ext(state),
        "seats",
        tuple(replace(s, stack=s.stack + 5, committed=s.committed) for s in seats),
    )
    with pytest.raises(ValueError, match="add up"):
        project_player_view(state, pid(0))
