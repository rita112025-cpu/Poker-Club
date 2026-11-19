"""P3-04: pot settlement (main and side pots, ties, odd chips, uncalled-bet return, showdown).

Independence: the expectations come from hand-worked examples of the approved contract; two
unrelated implementations are compared with the engine over every small case: a unit-by-unit
brute force written here, and a reference written by a separate agent from the contract text
alone. Not applicable: seat-by-seat betting rules (P3-03), registry integration (P3-05).
"""

import itertools
import random
from bisect import bisect_right
from typing import Any
from uuid import UUID

import pytest
from settlement_reference_independent import settle as agent_settle
from test_texas_engine import RULES, act, ext, new_hand, pid, shown_cards

from app.games.core import Card, Deck, GameResult, GameState, GameStatus
from app.games.texas_holdem import (
    Award,
    HandEnd,
    Pot,
    Refund,
    Settlement,
    TexasEngine,
    TexasPayload,
    build_pots,
    settle,
    settle_state,
)

# ---- worked examples of the contract ------------------------------------------------------


def nets(result: Settlement) -> dict[int, int]:
    return dict(result.deltas)


def test_example_1_one_short_all_in_makes_a_main_pot_and_a_side_pot() -> None:
    result = settle({0: 100, 1: 300, 2: 300}, set(), {0: (3, ()), 1: (2, ()), 2: (1, ())}, 2)
    assert result.refunds == () and [(p.amount, p.eligible) for p in result.pots] == [
        (300, (0, 1, 2)),
        (400, (1, 2)),
    ]
    assert nets(result) == {0: 200, 1: 100, 2: -300}


def test_example_2_an_uncalled_bet_is_returned_before_the_pot_is_built() -> None:
    result = settle({0: 500, 1: 200}, set(), {0: (1, ()), 1: (5, ())}, 0)
    assert result.refunds == (Refund(0, 300),)
    assert [(p.amount, p.eligible) for p in result.pots] == [(400, (0, 1))]
    assert nets(result) == {0: -200, 1: 200}


def test_example_3_folded_chips_count_but_never_win_and_equal_layers_merge() -> None:
    committed = {0: 100, 1: 300, 2: 300, 3: 200}
    result = settle(committed, {0}, {1: (1, ()), 2: (2, ()), 3: (3, ())}, 3)
    assert [(p.amount, p.eligible) for p in result.pots] == [(700, (1, 2, 3)), (200, (1, 2))]
    assert nets(result) == {0: -100, 1: -300, 2: -100, 3: 500}


def test_example_4_the_odd_chip_goes_clockwise_after_the_button() -> None:
    # A pot of 101 (seat 0 folded for 33; seats 1 and 4 tie with 34 each), button at seat 2.
    result = settle({0: 33, 1: 34, 4: 34}, {0}, {1: (5, ()), 4: (5, ())}, 2)
    assert nets(result) == {0: -33, 1: 50 - 34, 4: 51 - 34}  # seat 4 is first after the button


def test_example_5_two_layers_with_the_same_eligible_seats_are_one_pot() -> None:
    # Seats 0 and 3 fold after putting in 3 each; seats 1, 2, 4 put in 10 each and 1 and 2 tie.
    committed = {0: 3, 1: 10, 2: 10, 3: 3, 4: 10}
    result = settle(committed, {0, 3}, {1: (9, ()), 2: (9, ()), 4: (1, ())}, 0)
    assert [(p.amount, p.eligible) for p in result.pots] == [(36, (1, 2, 4))]  # 15 + 21
    assert nets(result) == {0: -3, 1: 8, 2: 8, 3: -3, 4: -10}  # 18 each, not 19 and 17


def test_the_button_seat_gets_an_odd_chip_last() -> None:
    strengths = {0: (1, ()), 1: (1, ()), 2: (0, ())}
    result = settle({0: 5, 1: 5, 2: 5}, set(), strengths, 1)
    # 15 chips, seats 0 and 1 tie: 7 each plus one chip; the order after the button (1) is
    # seat 2, seat 0, then the button itself, so seat 0 gets the extra chip and seat 1 does not
    assert nets(result) == {0: 3, 1: 2, 2: -5}


def test_a_lone_live_seat_wins_everything_without_any_strength() -> None:
    result = settle({0: 10, 1: 5, 2: 20}, {0, 1}, {}, 1)
    assert result.refunds == (Refund(2, 10),) and nets(result) == {0: -10, 1: -5, 2: 15}


# ---- an independent brute force: scan the pot one chip level at a time --------------------


def unit_scan(
    committed: dict[int, int], folded: set[int], strength: dict[int, int], button: int
) -> dict[int, int]:
    """Re-derives the contract without sorted levels: every chip level is looked at on its own."""
    seats = sorted(committed)
    order_all = seats[bisect_right(seats, button) :] + seats[: bisect_right(seats, button)]
    ranked = sorted(committed.values(), reverse=True)
    reduced = dict(committed)
    refund = {}
    if len(ranked) == 1 or ranked[0] > ranked[1]:
        holder = next(seat for seat, amount in committed.items() if amount == ranked[0])
        back = ranked[0] - (ranked[1] if len(ranked) > 1 else 0)
        refund[holder] = back
        reduced[holder] -= back
    pots: list[tuple[int, tuple[int, ...]]] = []
    previous: tuple[int, ...] | None = None
    for level in range(1, max(reduced.values()) + 1):
        paying = [seat for seat in seats if reduced[seat] >= level]
        eligible = tuple(seat for seat in paying if seat not in folded)
        if eligible == previous:
            pots[-1] = (pots[-1][0] + len(paying), eligible)
        else:
            pots.append((len(paying), eligible))
        previous = eligible
    result = {seat: -amount for seat, amount in committed.items()}
    for seat, amount in refund.items():
        result[seat] += amount
    for amount, eligible in pots:
        if len(eligible) == 1:
            result[eligible[0]] += amount
            continue
        top = max(strength[seat] for seat in eligible)
        winners = [seat for seat in order_all if seat in eligible and strength[seat] == top]
        for index in range(amount):  # hand the chips out one at a time, round robin
            result[winners[index % len(winners)]] += 1
    return result


def reachable(committed: dict[int, int], folded: set[int]) -> bool:
    top = max(committed.values())
    return any(amount == top and seat not in folded for seat, amount in committed.items())


def check_all(
    committed: dict[int, int], folded: set[int], strength: dict[int, int], button: int
) -> None:
    live = {seat: (strength[seat], ()) for seat in committed if seat not in folded}
    engine = nets(settle(committed, folded, live if len(live) > 1 else {}, button))
    brute = unit_scan(committed, folded, strength, button)
    agent = agent_settle(committed, folded, strength, button)
    assert engine == brute == agent, (committed, folded, strength, button, engine, brute, agent)
    assert sum(engine.values()) == 0


def test_every_small_table_agrees_with_both_independent_implementations() -> None:
    cases = 0
    for seats in ([0, 1], [0, 1, 2], [0, 2, 3]):
        for amounts in itertools.product(range(0, 7), repeat=len(seats)):
            committed = dict(zip(seats, amounts, strict=True))
            for fold_mask in range(2 ** len(seats)):
                folded = {s for i, s in enumerate(seats) if fold_mask >> i & 1}
                if len(folded) == len(seats) or not reachable(committed, folded):
                    continue
                live = [s for s in seats if s not in folded]
                for values in itertools.product(range(3), repeat=len(live)):
                    strength = dict(zip(live, values, strict=True))
                    for button in {seats[0], seats[-1], 1}:
                        check_all(committed, folded, strength, button)
                        cases += 1
    assert cases > 40_000


def test_random_larger_tables_agree_with_both_independent_implementations() -> None:
    generator = random.Random(20261117)
    for _ in range(6000):
        count = generator.randint(2, 9)
        seats = sorted(generator.sample(range(12), count))
        committed = {s: generator.choice([0, 1, 3, 5, 10, 25, 60, 100, 333]) for s in seats}
        folded = {s for s in seats if generator.random() < 0.35}
        if len(folded) == count or not reachable(committed, folded):
            continue
        live = [s for s in seats if s not in folded]
        strength = {s: generator.randint(0, 3) for s in live}
        check_all(committed, folded, strength, generator.choice(seats + [20]))


# ---- structural properties ---------------------------------------------------------------


def test_pots_are_conserved_never_won_by_folded_seats_and_awarded_in_full() -> None:
    generator = random.Random(5)
    for _ in range(2000):
        count = generator.randint(2, 7)
        seats = list(range(count))
        committed = {s: generator.randint(0, 50) for s in seats}
        folded = {s for s in seats if generator.random() < 0.4}
        if len(folded) == count or not reachable(committed, folded):
            continue
        strength = {s: (generator.randint(0, 2), ()) for s in seats if s not in folded}
        result = settle(
            committed, folded, strength if len(strength) > 1 else {}, generator.choice(seats)
        )
        refunds = sum(r.amount for r in result.refunds)
        assert refunds + sum(p.amount for p in result.pots) == sum(committed.values())
        for award in result.awards:
            assert award.seat not in folded
            assert award.seat in result.pots[award.pot].eligible
        for index, pot in enumerate(result.pots):
            assert sum(a.amount for a in result.awards if a.pot == index) == pot.amount
        assert all(a.amount > 0 for a in result.awards)


def test_invalid_input_is_rejected_without_guessing() -> None:
    ok = {0: 10, 1: 10}
    for committed, folded in [
        ({0: -1, 1: 5}, set()),
        ({0: True, 1: 5}, set()),
        ({0: 1.5, 1: 5}, set()),
        ({0: 5, 1: 5}, {0, 1}),  # nobody left
        ({0: 5, 1: 5}, {7}),  # not a table seat
        ({0: 50, 1: 5, 2: 5}, {0}),  # a folded seat holding the largest commitment
    ]:
        with pytest.raises((TypeError, ValueError)):
            build_pots(committed, folded)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="strength"):
        settle(ok, set(), {0: (1, ())}, 0)  # a contested pot needs every strength


def test_settlement_validates_its_own_numbers() -> None:
    pot = Pot(10, (0, 1))
    with pytest.raises(ValueError, match="in full"):
        Settlement((), (pot,), (Award(0, 0, 9),), ((0, 4), (1, -4)))
    with pytest.raises(ValueError, match="eligible"):
        Settlement((), (pot,), (Award(0, 2, 10),), ((0, -10), (2, 10)))
    with pytest.raises(ValueError, match="sum to zero"):
        Settlement((), (pot,), (Award(0, 0, 10),), ((0, 5), (1, -4)))
    for build in (
        lambda: Pot(-1, (0,)),
        lambda: Pot(5, ()),
        lambda: Pot(5, (1, 0)),
        lambda: Refund(0, -1),
        lambda: Award(0, 0, -1),
    ):
        with pytest.raises(ValueError):
            build()


# ---- end to end through the engine, with rigged hole cards and board ------------------------


def rigged(seats: list[int], button: int, hands: dict[int, str], board: str) -> Deck:
    """A deck that deals exactly these hole cards and board (no burning)."""
    ordered = sorted(seats)
    small = ordered[(ordered.index(button) + (0 if len(ordered) == 2 else 1)) % len(ordered)]
    start = ordered.index(small)
    order = ordered[start:] + ordered[:start]
    first = [Card.from_code(hands[s].split()[0]) for s in order]
    second = [Card.from_code(hands[s].split()[1]) for s in order]
    flop = [Card.from_code(c) for c in board.split()]
    used = {*first, *second, *flop}
    rest = [
        Card.from_code(r + s)
        for s in "SHDC"
        for r in ("A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2")
        if Card.from_code(r + s) not in used
    ]
    return Deck.for_testing([*first, *second, *flop, *rest])


def play_out(engine: TexasEngine, state: GameState) -> GameState:
    """Everyone checks or calls until the hand ends."""
    from app.games.texas_holdem import legal_actions

    while state.public.status is GameStatus.IN_PROGRESS:
        legal = legal_actions(state)
        assert legal is not None
        state, _ = act(engine, state, "check" if "check" in legal.kinds else "call")
    return state


def result_of(engine: TexasEngine, state: GameState) -> dict[int, tuple[int, int]]:
    result = engine.calculate_result(state)
    assert isinstance(result, GameResult)
    seat_of = {s.player_id: s.seat for s in ext(state).seats}
    return {seat_of[p.player_id]: (p.points_delta, p.rank) for p in result.players}


def test_heads_up_showdown_best_seven_card_hand_wins_the_pot() -> None:
    deck = rigged([0, 1], 0, {0: "AS AH", 1: "KS KH"}, "2C 7D 9H JC 3S")
    engine, state = new_hand({0: 100, 1: 100}, 0, RULES, deck)
    state = play_out(engine, state)
    assert ext(state).ended is HandEnd.SHOWDOWN
    assert {h.seat for h in ext(state).showdown} == {0, 1}
    assert result_of(engine, state) == {0: (10, 1), 1: (-10, 2)}


def test_a_tie_splits_the_pot_and_the_odd_chip_follows_the_button() -> None:
    # Both players in seat 0 and 2 play the board (a royal flush); seat 1 folded 5 first.
    deck = rigged([0, 1, 2], 0, {0: "2C 3D", 1: "4C 5D", 2: "2H 3S"}, "AS KS QS JS 10S")
    engine, state = new_hand({0: 100, 1: 100, 2: 100}, 0, RULES, deck)
    state, _ = act(engine, state, "call")  # seat 0
    state, _ = act(engine, state, "fold")  # seat 1, the small blind, gives up its 5
    state = play_out(engine, state)
    assert ext(state).pot == 25
    # 25 chips, a two-way tie: seat 2 is first after the button (0), so it gets the extra chip
    assert result_of(engine, state) == {0: (2, 2), 1: (-5, 3), 2: (3, 1)}


def test_a_short_all_in_wins_only_the_main_pot() -> None:
    deck = rigged([0, 1, 2], 0, {0: "AS AH", 1: "KS KH", 2: "QS QH"}, "2C 7D 9H JC 3S")
    engine, state = new_hand({0: 30, 1: 100, 2: 100}, 0, RULES, deck)
    state, _ = act(engine, state, "all_in")  # seat 0: 30 in total, a raise
    state, _ = act(engine, state, "call")  # seat 1 calls 30
    state, _ = act(engine, state, "call")  # seat 2 calls 30
    state, _ = act(engine, state, "bet", TexasPayload(50))  # seat 1 on the flop
    state, _ = act(engine, state, "call")  # seat 2
    state = play_out(engine, state)
    assert ext(state).pot == 190
    # seat 0 (aces) wins the 90 main pot; seat 1 (kings) beats seat 2 for the 100 side pot
    assert result_of(engine, state) == {0: (60, 1), 1: (20, 2), 2: (-80, 3)}


def test_an_uncalled_part_of_an_all_in_is_returned() -> None:
    deck = rigged([0, 1], 0, {0: "2C 3D", 1: "AS AH"}, "9H JC 4S 7D KD")
    engine, state = new_hand({0: 100, 1: 40}, 0, RULES, deck)
    state, _ = act(engine, state, "all_in")  # seat 0 shoves 100
    state, _ = act(engine, state, "all_in")  # seat 1 calls all-in for 40
    assert state.public.status is GameStatus.FINISHED
    assert result_of(engine, state) == {0: (-40, 2), 1: (40, 1)}  # 60 of the shove comes back


def test_a_folded_hand_is_never_shown_and_the_survivor_takes_the_pot() -> None:
    engine, state = new_hand({0: 100, 1: 100}, 0)
    state, _ = act(engine, state, "fold")
    assert ext(state).ended is HandEnd.LAST_STANDING and ext(state).showdown == ()
    assert result_of(engine, state) == {0: (-5, 2), 1: (5, 1)}


def test_shown_hands_are_the_real_hole_cards_of_the_seats_still_in() -> None:
    deck = rigged([0, 1, 2], 0, {0: "AS AH", 1: "KS KH", 2: "QS QH"}, "2C 7D 9H JC 3S")
    engine, state = new_hand({0: 100, 1: 100, 2: 100}, 0, RULES, deck)
    state, _ = act(engine, state, "fold")  # seat 0 folds
    state = play_out(engine, state)
    shown = {h.seat: h.cards for h in ext(state).showdown}
    assert set(shown) == {1, 2}  # the folded seat is not shown
    held = {p.player_id: p.hand for p in state.private.players}
    assert shown == {1: held[pid(1)], 2: held[pid(2)]}
    assert shown_cards(state) >= {c for cards in shown.values() for c in cards}


def test_ranks_share_a_place_for_equal_results() -> None:
    deck = rigged([0, 1, 2], 0, {0: "2C 3D", 1: "4C 5D", 2: "6H 8S"}, "AS KS QS JS 10S")
    engine, state = new_hand({0: 100, 1: 100, 2: 100}, 0, RULES, deck)
    state = play_out(engine, state)  # all three play the board: they split 30 equally
    assert result_of(engine, state) == {0: (0, 1), 1: (0, 1), 2: (0, 1)}
    engine, state = new_hand(
        {0: 100, 1: 100, 2: 100},
        0,
        RULES,
        rigged([0, 1, 2], 0, {0: "AH AD", 1: "KH KD", 2: "QH QD"}, "2C 7D 9H JC 3S"),
    )
    state, _ = act(engine, state, "fold")
    state = play_out(engine, state)
    ranks = result_of(engine, state)
    assert ranks[1][1] == 1 and ranks[2][1] == 3 and ranks[0][1] == 2  # +, -, -; best first


def test_settlement_does_not_change_the_state_and_is_repeatable() -> None:
    deck = rigged([0, 1], 0, {0: "AS AH", 1: "KS KH"}, "2C 7D 9H JC 3S")
    engine, state = new_hand({0: 100, 1: 100}, 0, RULES, deck)
    state = play_out(engine, state)
    before = state
    first = engine.calculate_result(state)
    assert first == engine.calculate_result(state) and state == before
    assert settle_state(state) == settle_state(state)
    assert sum(change for _, change in settle_state(state).deltas) == 0


def test_settling_an_unfinished_hand_or_a_foreign_state_is_refused() -> None:
    engine, state = new_hand({0: 100, 1: 100}, 0)
    with pytest.raises(ValueError, match="not finished"):
        settle_state(state)
    with pytest.raises(TypeError):
        settle_state(None)  # type: ignore[arg-type]
    plain: Any = UUID(int=1)
    with pytest.raises(TypeError):
        settle_state(plain)


# ---- engine end to end against the independent implementations ---------------------------------


def test_random_hands_settle_exactly_as_the_independent_implementations_do() -> None:
    from seven_card_reference_independent import evaluate7
    from test_texas_engine import pick_move

    from app.games.texas_holdem import legal_actions

    codes = [
        r + s
        for s in "SHDC"
        for r in ("A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2")
    ]
    generator = random.Random(20261118)
    showdowns = sides = ties = 0
    for _ in range(400):
        count = generator.randint(2, 6)
        seats = sorted(generator.sample(range(10), count))
        stacks = {s: generator.choice([3, 10, 25, 60, 150, 400]) for s in seats}
        order = list(codes)
        generator.shuffle(order)
        deck = Deck.for_testing(Card.from_code(c) for c in order)
        engine, state = new_hand(stacks, generator.choice(seats), RULES, deck)
        while state.public.status is GameStatus.IN_PROGRESS:
            legal = legal_actions(state)
            assert legal is not None
            kind, move = pick_move(generator, legal)
            state, _ = act(engine, state, kind, move)
        table = ext(state)
        committed = {s.seat: s.committed for s in table.seats}
        folded = {s.seat for s in table.seats if s.folded}
        strength: dict[int, int] = {}
        if table.ended is HandEnd.SHOWDOWN:
            showdowns += 1
            keyed = {
                h.seat: evaluate7([c.code for c in (*h.cards, *table.board)])
                for h in table.showdown
            }
            ordered = sorted(set(keyed.values()))
            strength = {seat: ordered.index(value) for seat, value in keyed.items()}
            ties += len(set(strength.values())) < len(strength)
        elif len(committed) - len(folded) != 1:
            raise AssertionError("a hand ended without a showdown or a lone survivor")
        expected_agent = agent_settle(committed, folded, strength, table.button_seat)
        expected_brute = unit_scan(committed, folded, strength, table.button_seat)
        got = dict(settle_state(state).deltas)
        assert got == expected_agent == expected_brute, (committed, folded, strength)
        sides += len(build_pots(committed, folded)[1]) > 1
        by_player = {p.player_id: p.points_delta for p in engine.calculate_result(state).players}  # type: ignore[union-attr]
        assert by_player == {s.player_id: got[s.seat] for s in table.seats}
    assert showdowns > 150 and sides > 20 and ties >= 1  # side pots and ties really occurred
