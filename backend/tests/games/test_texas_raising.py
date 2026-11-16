"""P3-03: no-limit bet, raise and all-in rules, minimum raises and re-opening of the action.

All flows are hand-computed against the fixed deck of test_texas_engine; rule values are TEST
FIXTURES (small blind 5, big blind 10). Amounts are raise-to totals for the betting round.
Not applicable: pots, settlement, side pots (P3-04), registry integration (P3-05).
"""

from typing import Any
from uuid import UUID

from engine_contract_suite import ContractScenario, check_engine_contract
from test_texas_engine import (
    CONFIG,
    NONE,
    RULES,
    SESSION,
    act,
    error_of,
    ext,
    new_hand,
    pid,
    turn_seat,
)

from app.games.core import GameAction, GameState, GameStatus, Player
from app.games.texas_holdem import (
    ActionTaken,
    HandEnd,
    TexasEngine,
    TexasPayload,
    legal_actions,
)


def amount(value: int) -> TexasPayload:
    return TexasPayload(value)


def seat_of(state: GameState, number: int) -> Any:
    return next(s for s in ext(state).seats if s.seat == number)


def to_flop_heads_up(stacks: dict[int, int]) -> tuple[TexasEngine, GameState]:
    engine, state = new_hand(stacks, 0)
    state, _ = act(engine, state, "call")  # seat 0, the small blind and button
    state, _ = act(engine, state, "check")  # seat 1, the big blind
    assert ext(state).street.value == "flop" and turn_seat(state) == 1
    return engine, state


def to_flop_three(stacks: dict[int, int]) -> tuple[TexasEngine, GameState]:
    engine, state = new_hand(stacks, 0)
    for kind in ("call", "call", "check"):  # seats 0, 1, then the big blind option
        state, _ = act(engine, state, kind)
    assert ext(state).street.value == "flop" and turn_seat(state) == 1
    return engine, state


# ---- minimum bet and raise chain ----------------------------------------------------------


def test_heads_up_bet_raise_and_short_all_in_chain() -> None:
    engine, state = to_flop_heads_up({0: 100, 1: 100})
    legal = legal_actions(state)
    assert legal is not None and legal.kinds == ("fold", "check", "all_in", "bet")
    assert (legal.min_to, legal.max_to) == (10, 90)

    state, events = act(engine, state, "bet", amount(30))
    assert events == (ActionTaken(1, "bet", 30, 30),)
    assert (ext(state).current_bet, ext(state).min_raise) == (30, 30)  # a full raise sets it

    legal = legal_actions(state)
    assert legal is not None and legal.kinds == ("fold", "call", "all_in", "raise")
    assert (legal.min_to, legal.max_to) == (60, 90) and legal.to_call == 30

    state, events = act(engine, state, "raise", amount(80))
    assert events == (ActionTaken(0, "raise", 80, 80),)
    assert (ext(state).current_bet, ext(state).min_raise) == (80, 50)

    legal = legal_actions(state)  # seat 1 holds 60 more: 90 in total, below the 130 minimum
    assert legal is not None and legal.kinds == ("fold", "call", "all_in")
    assert legal.min_to is None and legal.to_call == 50

    state, events = act(engine, state, "all_in")  # a SHORT raise to 90 (increment 10 < 50)
    assert events == (ActionTaken(1, "all_in", 60, 90),)
    assert (ext(state).current_bet, ext(state).min_raise) == (90, 50)  # increment unchanged
    assert seat_of(state, 1).all_in

    legal = legal_actions(state)  # one short all-in does not re-open the betting for seat 0
    assert legal is not None and legal.kinds == ("fold", "call", "all_in") and legal.to_call == 10
    assert error_of(engine, state, "raise", amount(150)).code == "illegal_action"

    state, _ = act(engine, state, "call")
    assert ext(state).ended is HandEnd.SHOWDOWN and ext(state).pot == 200
    assert state.public.status is GameStatus.FINISHED


def test_amount_boundaries_are_inclusive() -> None:
    engine, state = to_flop_heads_up({0: 100, 1: 100})
    assert error_of(engine, state, "bet", amount(9)).code == "bad_amount"
    assert error_of(engine, state, "bet", amount(91)).code == "bad_amount"
    assert error_of(engine, state, "bet", amount(0)).code == "bad_amount"
    low, _ = act(engine, state, "bet", amount(10))
    high, _ = act(engine, state, "bet", amount(90))
    assert seat_of(high, 1).all_in and seat_of(high, 1).stack == 0  # betting the stack is all-in
    assert seat_of(low, 1).stack == 80
    assert error_of(engine, low, "raise", amount(19)).code == "bad_amount"
    assert error_of(engine, low, "raise", amount(91)).code == "bad_amount"
    act(engine, low, "raise", amount(20))
    act(engine, low, "raise", amount(90))


def test_a_raise_to_the_full_stack_is_flagged_all_in() -> None:
    engine, state = new_hand({0: 100, 1: 100}, 0)
    state, events = act(engine, state, "raise", amount(100))  # seat 0 had posted 5
    assert events == (ActionTaken(0, "raise", 95, 100),)
    assert seat_of(state, 0).all_in and seat_of(state, 0).stack == 0
    assert (ext(state).current_bet, ext(state).min_raise) == (100, 90)


def test_preflop_raise_chain_updates_the_minimum_each_time() -> None:
    engine, state = new_hand({0: 1000, 1: 1000, 2: 1000}, 0)
    legal = legal_actions(state)
    assert legal is not None and (legal.min_to, legal.max_to) == (20, 1000)
    state, _ = act(engine, state, "raise", amount(30))  # increment 20 >= 10
    assert ext(state).min_raise == 20
    legal = legal_actions(state)  # seat 1 (small blind, 5 in)
    assert legal is not None and (legal.min_to, legal.to_call) == (50, 25)
    state, _ = act(engine, state, "raise", amount(70))  # increment 40
    assert ext(state).min_raise == 40
    legal = legal_actions(state)  # the big blind
    assert legal is not None and legal.min_to == 110
    state, events = act(engine, state, "raise", amount(110))  # increment 40 == minimum
    assert events == (ActionTaken(2, "raise", 100, 110),) and ext(state).min_raise == 40
    legal = legal_actions(state)  # seat 0 raised to 30 earlier; the bet has grown by 80 >= 40
    assert legal is not None and legal.min_to == 150 and legal.to_call == 80
    assert seat_of(state, 0).bet_seen == 30


def test_a_short_big_blind_still_means_a_minimum_raise_to_twice_the_blind() -> None:
    _, state = new_hand({0: 100, 1: 100, 2: 3}, 0)  # the big blind can only post 3
    assert ext(state).current_bet == 5  # the small blind's 5 is the highest bet
    legal = legal_actions(state)
    assert legal is not None and legal.to_call == 5 and legal.min_to == 20


def test_a_short_all_in_bet_does_not_change_the_minimum_increment() -> None:
    engine, state = to_flop_three({0: 100, 1: 16, 2: 100})  # seat 1 has 6 left on the flop
    legal = legal_actions(state)
    assert legal is not None and legal.kinds == ("fold", "check", "all_in")  # 6 < the 10 minimum
    state, events = act(engine, state, "all_in")
    assert events == (ActionTaken(1, "all_in", 6, 6),)
    assert (ext(state).current_bet, ext(state).min_raise) == (6, 10)
    legal = legal_actions(state)  # seat 2: the next raise is to at least 6 + 10
    assert legal is not None and legal.kinds == ("fold", "call", "all_in", "raise")
    assert legal.min_to == 16


def test_nobody_can_bet_or_raise_against_opponents_who_are_all_all_in() -> None:
    engine, state = to_flop_heads_up({0: 100, 1: 16})  # seat 1 has 6 left
    state, _ = act(engine, state, "all_in")  # a short all-in bet of 6
    legal = legal_actions(state)  # seat 0 is the only seat that can still act
    assert legal is not None and legal.kinds == ("fold", "call") and legal.to_call == 6
    assert error_of(engine, state, "raise", amount(50)).code == "illegal_action"


# ---- re-opening the action ---------------------------------------------------------------


def classic_spot() -> tuple[TexasEngine, GameState]:
    """Seat 1 bets 100, seat 2 raises to 300, short stacked seat 0 shoves to 350 (increment 50)."""
    engine, state = to_flop_three({0: 360, 1: 1000, 2: 1000})
    state, _ = act(engine, state, "bet", amount(100))  # seat 1
    state, _ = act(engine, state, "raise", amount(300))  # seat 2, increment 200
    assert ext(state).min_raise == 200 and turn_seat(state) == 0
    state, events = act(engine, state, "all_in")  # seat 0: 350 in total, a short raise
    assert events == (ActionTaken(0, "all_in", 350, 350),)
    assert (ext(state).current_bet, ext(state).min_raise) == (350, 200)
    return engine, state


def test_a_short_all_in_does_not_reopen_the_action_for_the_raiser() -> None:
    engine, state = classic_spot()
    assert turn_seat(state) == 1
    legal = legal_actions(state)  # the original bettor faces 250 more than it last saw
    assert legal is not None and "raise" in legal.kinds and legal.min_to == 550
    assert legal.to_call == 250 and legal.max_to == 990
    state, _ = act(engine, state, "call")
    assert turn_seat(state) == 2
    legal = legal_actions(state)  # the raiser saw 300; the bet grew by only 50 < 200
    assert legal is not None and legal.kinds == ("fold", "call") and legal.to_call == 50
    for kind, payload in (("raise", amount(600)), ("all_in", NONE), ("bet", amount(600))):
        assert error_of(engine, state, kind, payload).code == "illegal_action"
    state, _ = act(engine, state, "call")
    assert ext(state).street.value == "turn"


def test_a_full_raise_after_the_short_all_in_reopens_it_for_everyone() -> None:
    engine, state = classic_spot()
    state, events = act(engine, state, "raise", amount(600))  # seat 1: increment 250 >= 200
    assert events == (ActionTaken(1, "raise", 500, 600),) and ext(state).min_raise == 250
    assert turn_seat(state) == 2
    legal = legal_actions(state)  # the raiser's bet grew from 300 to 600: re-opened
    assert legal is not None and legal.kinds == ("fold", "call", "all_in", "raise")
    assert legal.min_to == 850 and legal.to_call == 300


def test_several_short_all_ins_that_add_up_to_a_full_raise_reopen_the_action() -> None:
    engine, state = new_hand({0: 230, 1: 1000, 2: 170, 3: 1000}, 0)
    while ext(state).street.value == "pre_flop":  # everyone limps; the big blind checks
        legal = legal_actions(state)
        assert legal is not None
        state, _ = act(engine, state, "check" if "check" in legal.kinds else "call")
    assert turn_seat(state) == 1
    state, _ = act(engine, state, "bet", amount(100))  # seat 1; minimum increment 100
    state, _ = act(engine, state, "all_in")  # seat 2: 160 in total, increment 60 < 100
    assert (ext(state).current_bet, ext(state).min_raise) == (160, 100)
    state, _ = act(engine, state, "call")  # seat 3 calls 160
    legal = legal_actions(state)  # seat 0 has not acted yet; 220 < 160 + 100
    assert legal is not None and legal.kinds == ("fold", "call", "all_in")
    state, _ = act(engine, state, "all_in")  # seat 0: 220 in total, increment 60 < 100
    assert (ext(state).current_bet, ext(state).min_raise) == (220, 100)
    assert turn_seat(state) == 1
    legal = legal_actions(state)  # 100 -> 220 is a growth of 120 >= 100: re-opened for seat 1
    assert legal is not None and legal.kinds[-1] == "raise" and legal.min_to == 320
    state, _ = act(engine, state, "call")
    assert turn_seat(state) == 3
    legal = legal_actions(state)  # seat 3 only saw 160 -> 220 (60 < 100): not re-opened for it
    assert legal is not None and legal.kinds == ("fold", "call") and legal.to_call == 60


def test_a_single_short_all_in_leaves_the_bettor_unable_to_raise() -> None:
    engine, state = to_flop_three({0: 1000, 1: 1000, 2: 170})
    state, _ = act(engine, state, "bet", amount(100))  # seat 1
    state, _ = act(engine, state, "all_in")  # seat 2: a short raise to 160
    state, _ = act(engine, state, "call")  # seat 0 (had not acted): calls 160
    assert turn_seat(state) == 1
    legal = legal_actions(state)  # the bet grew from 100 to 160: 60 < 100
    assert legal is not None and legal.kinds == ("fold", "call") and legal.to_call == 60


def test_the_big_blind_option_and_a_check_raise() -> None:
    engine, state = new_hand({0: 100, 1: 100, 2: 100}, 0)
    state, _ = act(engine, state, "call")
    state, _ = act(engine, state, "call")
    state, events = act(engine, state, "raise", amount(40))  # the option: raise to 40
    assert events == (ActionTaken(2, "raise", 30, 40),) and ext(state).street.value == "pre_flop"
    assert turn_seat(state) == 0  # everyone else must answer
    state, _ = act(engine, state, "call")
    state, _ = act(engine, state, "call")
    assert ext(state).street.value == "flop" and turn_seat(state) == 1
    state, _ = act(engine, state, "check")  # check ...
    state, events = act(engine, state, "bet", amount(20))  # seat 2 bets
    assert events == (ActionTaken(2, "bet", 20, 20),)
    legal = legal_actions(state)  # seat 0 has not acted this street
    assert legal is not None and legal.min_to == 40


def test_the_minimum_resets_on_every_street() -> None:
    engine, state = to_flop_heads_up({0: 1000, 1: 1000})
    state, _ = act(engine, state, "bet", amount(200))
    state, _ = act(engine, state, "call")
    assert ext(state).street.value == "turn"
    assert (ext(state).current_bet, ext(state).min_raise) == (0, 10)
    assert all(s.bet_seen == 0 and not s.acted for s in ext(state).seats)
    legal = legal_actions(state)
    assert legal is not None and legal.min_to == 10


# ---- rejections never change the state -----------------------------------------------------


def test_every_invalid_amount_or_payload_is_rejected_without_changing_the_state() -> None:
    engine, state = new_hand({0: 100, 1: 100, 2: 100}, 0)
    cases = [
        ("raise", NONE, "bad_payload"),
        ("bet", amount(50), "illegal_action"),
        ("raise", amount(19), "bad_amount"),
        ("raise", amount(101), "bad_amount"),
        ("raise", amount(0), "bad_amount"),
        ("call", amount(10), "bad_payload"),
        ("fold", amount(0), "bad_payload"),
        ("all_in", amount(100), "bad_payload"),
        ("check", NONE, "illegal_action"),
    ]
    for kind, payload, code in cases:
        assert error_of(engine, state, kind, payload).code == code, (kind, payload)
    for bad in (-1, True, 1.5, "20", None.__class__):
        try:
            TexasPayload(bad)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        raise AssertionError(f"{bad!r} was accepted as an amount")


# ---- creation: nothing to answer means no betting ----------------------------------------------


def test_a_lone_active_seat_with_nothing_to_answer_is_dealt_out_at_creation() -> None:
    # The big blind (stack 1) is all-in; the small blind has already put in more than that.
    _, state = new_hand({0: 400, 1: 1}, 0)
    table = ext(state)
    assert state.public.status is GameStatus.FINISHED and state.public.turn is None
    assert table.ended is HandEnd.SHOWDOWN and len(table.board) == 5 and table.pot == 6


def test_a_lone_active_seat_that_owes_chips_may_only_call_or_fold() -> None:
    # Small blind (3) and big blind (7) are all-in; seat 0 owes 7 but has nobody to raise against.
    engine, state = new_hand({0: 400, 1: 3, 2: 7}, 0)
    assert turn_seat(state) == 0
    legal = legal_actions(state)
    assert legal is not None and legal.kinds == ("fold", "call") and legal.to_call == 7
    assert error_of(engine, state, "raise", amount(50)).code == "illegal_action"
    assert error_of(engine, state, "all_in").code == "illegal_action"
    state, _ = act(engine, state, "call")
    assert ext(state).ended is HandEnd.SHOWDOWN and len(ext(state).board) == 5


# ---- the shared contract suite with real raising ---------------------------------------------


def test_the_contract_suite_passes_when_the_script_bets_and_raises() -> None:
    engine = TexasEngine(RULES)
    players = tuple(Player(pid(s), f"p{s}", s, 100) for s in (0, 1, 2))

    def next_legal(state: GameState) -> tuple[GameAction, TexasPayload] | None:
        legal = legal_actions(state)
        if legal is None or state.public.turn is None:
            return None
        version = state.public.state_version
        who = state.public.turn.player_id
        if legal.min_to is not None and version % 2 == 0:
            kind = "raise" if "raise" in legal.kinds else "bet"
            return GameAction(who, UUID(int=40 + version), version, kind), amount(legal.min_to)
        kind = "check" if "check" in legal.kinds else "call"
        return GameAction(who, UUID(int=40 + version), version, kind), NONE

    def illegal(state: GameState) -> tuple[GameAction, TexasPayload]:
        assert state.public.turn is not None
        return (
            GameAction(
                state.public.turn.player_id, UUID(int=60), state.public.state_version, "bet"
            ),
            amount(1),
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
        revealed=lambda state: frozenset(ext(state).board),
        results_supported=False,
    )
    check_engine_contract(engine, scenario)


def test_a_stack_that_exactly_covers_the_minimum_raise_may_raise_to_it() -> None:
    # Seat 0 will hold exactly 20 in total: the minimum raise-to (10 + 10) and also all-in.
    engine, state = new_hand({0: 20, 1: 100, 2: 100}, 0)
    legal = legal_actions(state)
    assert legal is not None and legal.kinds == ("fold", "call", "all_in", "raise")
    assert (legal.min_to, legal.max_to) == (20, 20)
    state, events = act(engine, state, "raise", amount(20))
    assert events == (ActionTaken(0, "raise", 20, 20),) and seat_of(state, 0).all_in
    assert (ext(state).current_bet, ext(state).min_raise) == (20, 10)


def test_a_check_records_the_bet_the_seat_faced() -> None:
    engine, state = new_hand({0: 100, 1: 100, 2: 100}, 0)
    state, _ = act(engine, state, "call")
    state, _ = act(engine, state, "call")
    state, _ = act(engine, state, "check")  # the big blind checks its option facing 10
    assert ext(state).street.value == "flop"
    engine2, state2 = new_hand({0: 100, 1: 100}, 0)
    state2, _ = act(engine2, state2, "call")
    legal = legal_actions(state2)
    assert legal is not None and legal.to_call == 0
    state2, _ = act(engine2, state2, "check")
    assert all(s.bet_seen == 0 for s in ext(state2).seats)  # a new street starts from zero
