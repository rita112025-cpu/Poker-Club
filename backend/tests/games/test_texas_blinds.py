"""P3-04-0 (tests only): the betting rules with blind structures other than 5/10, and a spot
where an opponent has folded and the rest are all-in.

Closes the P3-03 coverage reservations: every earlier test used 5/10 only, so a regression
that hard-coded the big blind, or counted folded seats as opponents who can still act,
would not have been noticed.
"""

import pytest
from test_texas_engine import act, error_of, ext, new_hand, turn_seat

from app.games.texas_holdem import HandEnd, TexasPayload, TexasRules, legal_actions

BLINDS = [(1, 2), (3, 7), (25, 50), (100, 250)]


def rules(small: int, big: int) -> TexasRules:
    return TexasRules("blinds", small, big, False)


@pytest.mark.parametrize("small,big", BLINDS)
def test_minimum_bet_and_raise_follow_the_configured_big_blind(small: int, big: int) -> None:
    engine, state = new_hand({0: 100_000, 1: 100_000, 2: 100_000}, 0, rules(small, big))
    assert ext(state).min_raise == big and ext(state).current_bet == big
    legal = legal_actions(state)  # seat 0, first to act, facing the big blind
    assert legal is not None and legal.to_call == big
    assert (legal.min_to, legal.max_to) == (2 * big, 100_000)
    state, _ = act(engine, state, "raise", TexasPayload(3 * big))  # increment 2 * big
    assert ext(state).min_raise == 2 * big
    legal = legal_actions(state)  # small blind: raise to 3 * big + 2 * big
    assert legal is not None and legal.min_to == 5 * big and legal.to_call == 3 * big - small
    state, _ = act(engine, state, "call")
    state, _ = act(engine, state, "call")
    assert ext(state).street.value == "flop" and ext(state).min_raise == big
    legal = legal_actions(state)  # nothing bet yet: the minimum bet is one big blind
    assert legal is not None and legal.min_to == big and "bet" in legal.kinds


@pytest.mark.parametrize("small,big", BLINDS)
def test_a_short_big_blind_still_means_a_raise_to_twice_the_big_blind(small: int, big: int) -> None:
    short = big - 1  # the big blind can only post this much and is all-in
    _, state = new_hand({0: 100_000, 1: 100_000, 2: short}, 0, rules(small, big))
    assert ext(state).current_bet == max(small, short)
    legal = legal_actions(state)
    assert legal is not None and legal.min_to == 2 * big


@pytest.mark.parametrize("small,big", BLINDS)
def test_every_street_resets_the_minimum_to_the_big_blind(small: int, big: int) -> None:
    engine, state = new_hand({0: 100_000, 1: 100_000}, 0, rules(small, big))
    state, _ = act(engine, state, "raise", TexasPayload(5 * big))
    state, _ = act(engine, state, "call")
    assert ext(state).street.value == "flop"
    assert (ext(state).current_bet, ext(state).min_raise) == (0, big)
    state, _ = act(engine, state, "bet", TexasPayload(7 * big))
    assert ext(state).min_raise == 7 * big
    state, _ = act(engine, state, "call")
    assert ext(state).street.value == "turn" and ext(state).min_raise == big


def test_a_seat_cannot_raise_when_the_opponents_left_are_folded_or_all_in() -> None:
    # Seat 1 (small blind, 3) and seat 2 (big blind, 7) are all-in; seat 3 folds first, so
    # seat 0 is the only seat that can still act and has nobody to raise against.
    engine, state = new_hand({0: 400, 1: 3, 2: 7, 3: 400}, 0)
    assert turn_seat(state) == 3
    legal = legal_actions(state)
    assert legal is not None and "raise" in legal.kinds  # seat 0 is still able to act
    state, _ = act(engine, state, "fold")
    assert turn_seat(state) == 0
    legal = legal_actions(state)
    assert legal is not None and legal.kinds == ("fold", "call") and legal.to_call == 7
    for kind, payload in (("raise", TexasPayload(50)), ("all_in", TexasPayload())):
        assert error_of(engine, state, kind, payload).code == "illegal_action"
    state, _ = act(engine, state, "call")
    assert ext(state).ended is HandEnd.SHOWDOWN and len(ext(state).board) == 5
