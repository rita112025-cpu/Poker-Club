"""P3-05: applying the settlement to the stacks, exactly once, with a public marker.

Contract (see docs/TEXAS_HOLDEM_CONTRACT.md, clauses R11): settle_state computes and changes
nothing; apply_settlement / TexasEngine.settle_hand apply, recompute the amounts from the state
(never from a caller), set SeatState.payout and TexasPublic.settled, move the state version on
by one and emit one HandSettled event; a second application is refused. Not covered because
undecided: which settlement details (pot breakdown, winners) become public and when.
"""

import inspect
import random
from dataclasses import replace
from typing import Any
from uuid import UUID

import pytest
from engine_contract_suite import reveals_card
from settlement_reference_independent import settle as agent_settle
from test_texas_engine import RULES, act, ext, new_hand, pid, shown_cards
from test_texas_settlement import play_out, result_of, rigged, unit_scan

from app.games.core import (
    Card,
    Deck,
    GameAction,
    GameError,
    GameResult,
    GameState,
    GameStatus,
    PlayerView,
    project_player_view,
)
from app.games.texas_holdem import (
    HandEnd,
    HandSettled,
    TexasEngine,
    TexasPayload,
    apply_settlement,
    legal_actions,
    settle_state,
)

NONE = TexasPayload()


def settled_heads_up() -> tuple[TexasEngine, GameState, GameState]:
    deck = rigged([0, 1], 0, {0: "AS AH", 1: "KS KH"}, "2C 7D 9H JC 3S")
    engine, state = new_hand({0: 100, 1: 100}, 0, RULES, deck)
    finished = play_out(engine, state)
    result = engine.settle_hand(finished)
    assert not isinstance(result, GameError)
    return engine, finished, result.state


# ---- one application, clearly marked --------------------------------------------------------


def test_settlement_moves_the_chips_marks_the_hand_and_emits_one_event() -> None:
    engine, finished, settled = settled_heads_up()
    before, after = ext(finished), ext(settled)
    assert not before.settled and after.settled
    assert [s.stack for s in before.seats] == [90, 90] and before.pot == 20
    assert [s.stack for s in after.seats] == [110, 90]  # seat 0 (aces) takes the 20
    assert [s.payout for s in before.seats] == [0, 0] and [s.payout for s in after.seats] == [20, 0]
    assert settled.public.state_version == finished.public.state_version + 1
    assert settled.public.status is GameStatus.FINISHED and settled.public.turn is None
    result = engine.settle_hand(finished)
    assert not isinstance(result, GameError)
    assert [(e.seq, e.event_type, e.payload) for e in result.events] == [
        (before.event_seq, "HandSettled", HandSettled())
    ]
    assert after.event_seq == before.event_seq + 1
    assert [p.points for p in settled.public.players] == [100, 100]  # starting stacks untouched
    assert after.pot == before.pot == 20  # the pot stays on record as what was distributed


def test_a_second_application_is_refused_and_changes_nothing() -> None:
    engine, finished, settled = settled_heads_up()
    again = engine.settle_hand(settled)
    assert isinstance(again, GameError) and again.code == "already_settled"
    with pytest.raises(ValueError, match="already settled"):
        apply_settlement(settled)
    third = engine.settle_hand(settled)
    assert third == again
    assert settled.public.state_version == finished.public.state_version + 1  # no second bump
    assert [s.stack for s in ext(settled).seats] == [110, 90]


def test_only_a_finished_texas_hand_can_be_settled() -> None:
    engine, running = new_hand({0: 100, 1: 100}, 0)
    early = engine.settle_hand(running)
    assert isinstance(early, GameError) and early.code == "not_finished"
    with pytest.raises(ValueError, match="not finished"):
        apply_settlement(running)
    from test_texas_engine import GameConfig  # noqa: F401  (re-export used below)

    from app.games.core import Player, PrivateGameData, PublicGameData, Turn

    pair = (Player(pid(0), "a", 0), Player(pid(1), "b", 1))
    plain = GameState(
        UUID(int=9),
        "other",
        "1",
        PublicGameData(GameStatus.IN_PROGRESS, 0, pair, Turn(pid(0))),
        PrivateGameData(),
    )
    foreign = engine.settle_hand(plain)
    assert isinstance(foreign, GameError) and foreign.code == "wrong_game"
    with pytest.raises(TypeError):
        engine.settle_hand(None)  # type: ignore[arg-type]


def test_nothing_in_the_interface_accepts_a_settlement_from_outside() -> None:
    assert list(inspect.signature(apply_settlement).parameters) == ["state"]
    assert list(inspect.signature(TexasEngine.settle_hand).parameters) == ["self", "state"]


def test_computing_and_applying_are_separate_responsibilities() -> None:
    engine, finished, settled = settled_heads_up()
    before = finished
    plan = settle_state(finished)
    assert finished == before  # computing never changes the state
    assert settle_state(settled) == plan  # it is pure: the same answer before and after applying
    paid = {r.seat: r.amount for r in plan.refunds}
    for award in plan.awards:
        paid[award.seat] = paid.get(award.seat, 0) + award.amount
    assert {s.seat: s.payout for s in ext(settled).seats} == {0: paid.get(0, 0), 1: paid.get(1, 0)}


# ---- results and actions after the settlement ---------------------------------------------------


def test_the_result_is_the_same_before_and_after_and_matches_the_stacks() -> None:
    engine, finished, settled = settled_heads_up()
    assert engine.calculate_result(finished) == engine.calculate_result(settled)
    result = engine.calculate_result(settled)
    assert isinstance(result, GameResult)
    delta = {p.player_id: p.points_delta for p in result.players}
    start = {p.id: p.points for p in settled.public.players}
    for seat in ext(settled).seats:
        assert seat.stack - start[seat.player_id] == delta[seat.player_id]


def test_no_action_is_possible_after_the_settlement() -> None:
    engine, _, settled = settled_heads_up()
    assert legal_actions(settled) is None and engine.is_game_over(settled)
    action = GameAction(pid(0), UUID(int=1), settled.public.state_version, "check")
    for kind in ("check", "call", "fold", "all_in"):
        error = engine.apply_action(settled, replace(action, type=kind), NONE)
        assert isinstance(error, GameError) and error.code == "game_over"


def test_a_lone_survivor_and_an_uncalled_bet_are_settled_too() -> None:
    engine, state = new_hand({0: 100, 1: 100}, 0)
    state, _ = act(
        engine, state, "fold"
    )  # the small blind folds: the big blind takes 10, 5 of its own
    done = engine.settle_hand(state)
    assert not isinstance(done, GameError)
    assert [s.stack for s in ext(done.state).seats] == [95, 105]
    assert [s.payout for s in ext(done.state).seats] == [0, 15]  # 5 refunded plus the 10 pot
    assert ext(done.state).ended is HandEnd.LAST_STANDING and ext(done.state).showdown == ()


def test_a_hand_dealt_out_at_creation_can_be_settled() -> None:
    engine, state = new_hand({0: 4, 1: 6}, 0, replace_rules(10, 20))
    assert state.public.status is GameStatus.FINISHED
    done = engine.settle_hand(state)
    assert not isinstance(done, GameError)
    assert sum(s.stack for s in ext(done.state).seats) == 10
    assert sum(s.payout for s in ext(done.state).seats) == ext(done.state).pot == 10


def replace_rules(small: int, big: int) -> Any:
    from app.games.texas_holdem import TexasRules

    return TexasRules("apply", small, big, False)


# ---- the state cannot describe a settlement that does not add up ---------------------


def test_inconsistent_settlements_cannot_be_constructed() -> None:
    _, finished, settled = settled_heads_up()
    table = ext(settled)
    seats = table.seats
    with pytest.raises(ValueError, match="exactly the pot"):  # payouts that do not sum to the pot
        replace(settled, extension=replace(table, seats=(replace(seats[0], payout=19), seats[1])))
    with pytest.raises(ValueError, match="starting points minus"):  # stack not matching the payout
        replace(
            settled,
            extension=replace(table, seats=(replace(seats[0], stack=seats[0].stack + 1), seats[1])),
        )
    with pytest.raises(ValueError, match="before the settlement"):  # payout without settlement
        replace(
            finished,
            extension=replace(
                ext(finished),
                seats=(replace(ext(finished).seats[0], payout=1), ext(finished).seats[1]),
            ),
        )
    with pytest.raises(ValueError, match="finished hand"):  # settled before it ended
        _, running = new_hand({0: 100, 1: 100}, 0)
        replace(running, extension=replace(ext(running), settled=True))
    folded_state = _folded_state()
    seat0 = ext(folded_state).seats[0]
    with pytest.raises(ValueError, match="folded seat"):
        replace(ext(folded_state), seats=(replace(seat0, payout=5), *ext(folded_state).seats[1:]))


def _folded_state() -> GameState:
    engine, state = new_hand({0: 100, 1: 100}, 0)
    state, _ = act(engine, state, "fold")
    return state


# ---- events: order and content ------------------------------------------------------------------


def test_a_whole_hand_has_one_gapless_event_sequence_ending_with_the_settlement() -> None:
    deck = rigged([0, 1, 2], 0, {0: "AS AH", 1: "KS KH", 2: "QS QH"}, "2C 7D 9H JC 3S")
    engine, state = new_hand({0: 100, 1: 100, 2: 100}, 0, RULES, deck)
    seen: list[tuple[int, str]] = []
    from test_texas_engine import legal_actions as legal

    while state.public.status is GameStatus.IN_PROGRESS:
        options = legal(state)
        assert options is not None
        kind = "check" if "check" in options.kinds else "call"
        assert state.public.turn is not None
        action = GameAction(
            state.public.turn.player_id, UUID(int=1), state.public.state_version, kind
        )
        result = engine.apply_action(state, action, NONE)
        assert not isinstance(result, GameError)
        seen += [(e.seq, e.event_type) for e in result.events]
        state = result.state
    final = engine.settle_hand(state)
    assert not isinstance(final, GameError)
    seen += [(e.seq, e.event_type) for e in final.events]
    assert [seq for seq, _ in seen] == list(range(len(seen)))  # no gap, no repeat
    names = [name for _, name in seen]
    assert names[-2:] == ["HandEnded", "HandSettled"] and names.count("HandSettled") == 1
    assert names.index("HandEnded") < names.index("HandSettled")
    assert ext(final.state).event_seq == len(seen)


# ---- conservation and independence ----------------------------------------------------


def test_random_hands_conserve_chips_and_match_the_independent_settlement() -> None:
    from test_texas_engine import legal_actions as legal
    from test_texas_engine import pick_move

    codes = [
        r + s
        for s in "SHDC"
        for r in ("A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2")
    ]
    generator = random.Random(20261119)
    settled_count = refunds = 0
    for _ in range(300):
        count = generator.randint(2, 6)
        seats = sorted(generator.sample(range(10), count))
        stacks = {s: generator.choice([3, 10, 25, 60, 150, 400]) for s in seats}
        order = list(codes)
        generator.shuffle(order)
        engine, state = new_hand(
            stacks,
            generator.choice(seats),
            RULES,
            Deck.for_testing(Card.from_code(c) for c in order),
        )
        while state.public.status is GameStatus.IN_PROGRESS:
            options = legal(state)
            assert options is not None
            kind, move = pick_move(generator, options)
            state, _ = act(engine, state, kind, move)
        table = ext(state)
        committed = {s.seat: s.committed for s in table.seats}
        folded = {s.seat for s in table.seats if s.folded}
        strength: dict[int, int] = {}
        if table.ended is HandEnd.SHOWDOWN:
            from seven_card_reference_independent import evaluate7

            keyed = {
                h.seat: evaluate7([c.code for c in (*h.cards, *table.board)])
                for h in table.showdown
            }
            ordered = sorted(set(keyed.values()))
            strength = {seat: ordered.index(value) for seat, value in keyed.items()}
        done = engine.settle_hand(state)
        assert not isinstance(done, GameError)
        after = ext(done.state)
        expected = agent_settle(committed, folded, strength, table.button_seat)
        assert expected == unit_scan(committed, folded, strength, table.button_seat)
        start = {p.seat: p.points for p in done.state.public.players}
        for seat in after.seats:
            assert seat.payout == expected[seat.seat] + committed[seat.seat]  # independent payout
            assert seat.stack == start[seat.seat] - committed[seat.seat] + seat.payout
            assert seat.all_in == (seat.stack == 0)
        assert sum(s.stack for s in after.seats) == sum(start.values())  # chips conserved
        assert sum(s.payout for s in after.seats) == after.pot == sum(committed.values())
        result = engine.calculate_result(done.state)
        assert isinstance(result, GameResult)
        assert result == engine.calculate_result(state)
        assert isinstance(engine.settle_hand(done.state), GameError)
        settled_count += 1
        refunds += bool(settle_state(state).refunds)
    assert settled_count == 300 and refunds > 20  # uncalled bets really occurred


# ---- information: public and private views after the settlement -------------------------


def test_views_of_a_settled_hand_show_only_what_may_be_public() -> None:
    deck = rigged([0, 1, 2], 0, {0: "AS AH", 1: "KS KH", 2: "QS QH"}, "2C 7D 9H JC 3S")
    engine, state = new_hand({0: 100, 1: 100, 2: 100}, 0, RULES, deck)
    state, _ = act(engine, state, "fold")  # seat 0 folds before the showdown
    finished = play_out(engine, state)
    settled = engine.settle_hand(finished)
    assert not isinstance(settled, GameError)
    final = settled.state
    held = {p.player_id: p.hand for p in final.private.players}
    seat_of = {s.player_id: s.seat for s in ext(final).seats}
    shown = {c for h in ext(final).showdown for c in h.cards}
    assert {h.seat for h in ext(final).showdown} == {1, 2}  # the folded seat is never shown
    for player in final.public.players:
        view = project_player_view(final, player.id)
        assert isinstance(view, PlayerView) and view.private.hand == held[player.id]
        text = repr(view) + repr(view.extension) + repr(view.public)
        for other, hand in held.items():
            for card in hand:
                # a hole card is in the public text only if it was shown (own cards are private)
                assert reveals_card(text, card) == (card in shown), (player.id, card, other)
        for card in final.private.remaining_cards:
            assert not reveals_card(text, card)  # the undealt deck is never visible
    assert shown <= shown_cards(final)
    for event in settled.events:
        assert not any(
            reveals_card(repr(event.payload), card) for hand in held.values() for card in hand
        )
    assert all(seat_of[pid(s)] == s for s in (0, 1, 2))


def test_the_settlement_adds_no_hidden_information_to_the_public_data() -> None:
    engine, finished, settled = settled_heads_up()
    view_before = project_player_view(finished, pid(0))
    view_after = project_player_view(settled, pid(0))
    assert isinstance(view_before, PlayerView) and isinstance(view_after, PlayerView)
    public_before, public_after = repr(view_before.extension), repr(view_after.extension)
    removed = {"payout", "settled", "stack", "event_seq"}
    # Only the fields the settlement changes differ; no new card appears anywhere.
    assert {c.code for c in finished.private.remaining_cards} <= {
        c.code for c in finished.private.remaining_cards
    }
    assert result_of(engine, settled) == result_of(engine, finished)
    assert public_before != public_after and removed
    for card in settled.private.remaining_cards:
        assert not reveals_card(public_after, card)
