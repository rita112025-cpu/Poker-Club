"""Pot settlement for a finished Texas hand (P3-04): pure functions, no engine or state change.

Contract (approved wording):
1. Uncalled return: let top be the largest commitment and second the largest among all OTHER
   seats (folded and all-in seats included). If a single seat holds the top, top - second
   chips go back to it and its commitment becomes second. This happens once, first.
2. Layers: take the distinct positive commitment levels L1 < L2 < ... (after step 1). Layer i
   holds sum over seats of min(c, Li) - min(c, L(i-1)); its ELIGIBLE seats are the seats that
   did not fold and have c >= Li. Folded chips count, folded seats never win.
3. Adjacent layers with identical eligible seats are merged before they are split; otherwise
   two odd remainders would favour the first winner twice.
4. A pot goes to the eligible seat(s) with the best hand; a lone eligible seat takes it without
   a comparison. Ties split equally; the remainder is handed out one chip at a time starting
   with the first tied seat clockwise after the button and ending with the button itself. Each
   pot is split on its own.
5. With one seat left the hand is not compared and nothing is shown; that seat takes everything.
6. A seat's net change = refund + winnings - its commitment; the nets sum to zero.

Seat numbers increase clockwise and wrap. A folded seat holding the largest commitment, or a
layer nobody can win, cannot arise in a real hand and is rejected (fail closed).
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass, replace

from app.games.core.extensions import EventPayload
from app.games.core.models import GameState, GameStatus
from app.games.core.validation import (
    require_exact,
    require_exact_tuple,
    require_nonnegative_int,
)
from app.games.texas_holdem.events import HandSettled
from app.games.texas_holdem.hands import best_of_seven
from app.games.texas_holdem.state import HandEnd, TexasPublic

Strength = tuple[int, tuple[int, ...]]


@dataclass(frozen=True, slots=True)
class Refund:
    seat: int
    amount: int

    def __post_init__(self) -> None:
        require_nonnegative_int(self.seat, "seat")
        require_nonnegative_int(self.amount, "amount")


@dataclass(frozen=True, slots=True)
class Pot:
    amount: int
    eligible: tuple[int, ...]  # seats, increasing

    def __post_init__(self) -> None:
        require_nonnegative_int(self.amount, "amount")
        if type(self.eligible) is not tuple or any(type(s) is not int for s in self.eligible):
            raise TypeError("eligible must be a tuple of integers")
        if not self.eligible or list(self.eligible) != sorted(set(self.eligible)):
            raise ValueError("a pot needs unique, increasing eligible seats")


@dataclass(frozen=True, slots=True)
class Award:
    pot: int  # index into Settlement.pots
    seat: int
    amount: int

    def __post_init__(self) -> None:
        require_nonnegative_int(self.pot, "pot")
        require_nonnegative_int(self.seat, "seat")
        require_nonnegative_int(self.amount, "amount")


@dataclass(frozen=True, slots=True)
class Settlement:
    refunds: tuple[Refund, ...]
    pots: tuple[Pot, ...]
    awards: tuple[Award, ...]
    deltas: tuple[tuple[int, int], ...]  # (seat, net chip change), by increasing seat

    def __post_init__(self) -> None:
        require_exact_tuple(self.refunds, Refund, "refunds")
        require_exact_tuple(self.pots, Pot, "pots")
        require_exact_tuple(self.awards, Award, "awards")
        if type(self.deltas) is not tuple:
            raise TypeError("deltas must be a tuple")
        for pair in self.deltas:
            if type(pair) is not tuple or len(pair) != 2:
                raise TypeError("each delta is a (seat, change) pair")
            if type(pair[0]) is not int or type(pair[1]) is not int:
                raise TypeError("delta values must be integers")
        for index, pot in enumerate(self.pots):
            given = sum(a.amount for a in self.awards if a.pot == index)
            if given != pot.amount:
                raise ValueError("every pot must be awarded in full")
            if any(a.seat not in pot.eligible for a in self.awards if a.pot == index):
                raise ValueError("only eligible seats can win a pot")
        if sum(change for _, change in self.deltas) != 0:
            raise ValueError("chips must be conserved; changes must sum to zero")


def build_pots(
    committed: Mapping[int, int], folded: Collection[int]
) -> tuple[tuple[Refund, ...], tuple[Pot, ...]]:
    """Steps 1-3: the uncalled-bet refund and the merged pots, without any hand comparison."""
    for seat, amount in committed.items():
        require_nonnegative_int(seat, "seat")
        require_nonnegative_int(amount, "commitment")
    out = set(folded)
    if not out <= set(committed):
        raise ValueError("a folded seat must be a table seat")
    live = [seat for seat in sorted(committed) if seat not in out]
    if not live:
        raise ValueError("at least one seat must still be in the hand")
    levels = dict(committed)
    refunds: list[Refund] = []
    top = max(levels.values())
    holders = [seat for seat, amount in levels.items() if amount == top]
    if any(seat in out for seat in holders) and not any(seat not in out for seat in holders):
        raise ValueError("a folded seat cannot hold the largest commitment")
    if len(holders) == 1:
        others = [amount for seat, amount in levels.items() if seat != holders[0]]
        second = max(others, default=0)
        if top > second:
            refunds.append(Refund(holders[0], top - second))
            levels[holders[0]] = second
    steps = sorted({amount for amount in levels.values() if amount > 0})
    pots: list[Pot] = []
    previous = 0
    for level in steps:
        amount = sum(min(c, level) - min(c, previous) for c in levels.values())
        eligible = tuple(seat for seat in live if levels[seat] >= level)
        if not eligible:
            raise ValueError("a layer nobody can win cannot arise in a real hand")
        if pots and pots[-1].eligible == eligible:
            pots[-1] = Pot(pots[-1].amount + amount, eligible)
        else:
            pots.append(Pot(amount, eligible))
        previous = level
    return tuple(refunds), tuple(pots)


def odd_chip_order(winners: Collection[int], button: int) -> list[int]:
    """Clockwise from the seat after the button; the button itself comes last."""
    return sorted(winners, key=lambda seat: (seat <= button, seat))


def split_pot(
    index: int, pot: Pot, strengths: Mapping[int, Strength], button: int
) -> tuple[Award, ...]:
    """Step 4 for one pot."""
    if len(pot.eligible) == 1:
        return (Award(index, pot.eligible[0], pot.amount),)
    if any(seat not in strengths for seat in pot.eligible):
        raise ValueError("a contested pot needs a hand strength for every eligible seat")
    best = max(strengths[seat] for seat in pot.eligible)
    winners = [seat for seat in pot.eligible if strengths[seat] == best]
    share, extra = divmod(pot.amount, len(winners))
    awards = []
    for position, seat in enumerate(odd_chip_order(winners, button)):
        amount = share + (1 if position < extra else 0)
        if amount:
            awards.append(Award(index, seat, amount))
    return tuple(awards)


def settle(
    committed: Mapping[int, int],
    folded: Collection[int],
    strengths: Mapping[int, Strength],
    button: int,
) -> Settlement:
    """Steps 1-6. `strengths` is needed for every live seat when two or more are left."""
    refunds, pots = build_pots(committed, folded)
    awards: list[Award] = []
    for index, pot in enumerate(pots):
        awards.extend(split_pot(index, pot, strengths, button))
    net = {seat: -amount for seat, amount in committed.items()}
    for refund in refunds:
        net[refund.seat] += refund.amount
    for award in awards:
        net[award.seat] += award.amount
    return Settlement(refunds, pots, tuple(awards), tuple(sorted(net.items())))


def settle_state(state: GameState) -> Settlement:
    """Settle a finished Texas hand from its state (server side: reads the hole cards)."""
    require_exact(state, GameState, "state")
    table = state.extension
    if not isinstance(table, TexasPublic):
        raise TypeError("state has no Texas table data")
    if state.public.status is not GameStatus.FINISHED:
        raise ValueError("the hand is not finished")
    committed = {seat.seat: seat.committed for seat in table.seats}
    folded = {seat.seat for seat in table.seats if seat.folded}
    strengths: dict[int, Strength] = {}
    if table.ended is HandEnd.SHOWDOWN:
        hands = {item.player_id: item.hand for item in state.private.players}
        for seat in table.seats:
            if not seat.folded:
                strengths[seat.seat] = best_of_seven(
                    (*hands[seat.player_id], *table.board)
                ).sort_key
    return settle(committed, folded, strengths, table.button_seat)


def apply_settlement(state: GameState) -> tuple[GameState, list[EventPayload]]:
    """Apply the settlement of a finished hand to the stacks, ONCE.

    This is the only place that changes chips after a hand: settle_state computes (pure) and
    this function applies. Each seat's stack grows by its payout (refund plus winnings), the
    payout is recorded on the seat, `settled` is set and the state version moves on by one with
    one HandSettled event. A second call is refused (the marker), so a result can never be
    applied twice, and nothing here accepts a settlement from outside: the amounts are always
    recomputed from the state itself.
    """
    settlement = settle_state(state)
    table = state.extension
    if not isinstance(table, TexasPublic):
        raise TypeError("state has no Texas table data")
    if table.settled:
        raise ValueError("the hand is already settled")
    gained: dict[int, int] = {}
    for refund in settlement.refunds:
        gained[refund.seat] = gained.get(refund.seat, 0) + refund.amount
    for award in settlement.awards:
        gained[award.seat] = gained.get(award.seat, 0) + award.amount
    seats = tuple(
        replace(
            seat,
            stack=seat.stack + gained.get(seat.seat, 0),
            payout=gained.get(seat.seat, 0),
            all_in=seat.stack + gained.get(seat.seat, 0) == 0,
        )
        for seat in table.seats
    )
    if sum(gained.values()) != table.pot:
        raise ValueError("the settlement must distribute exactly the pot")
    if sum(seat.stack for seat in seats) != sum(player.points for player in state.public.players):
        raise ValueError("chips must be conserved by the settlement")
    events: list[EventPayload] = [HandSettled()]
    new_table = replace(table, seats=seats, settled=True, event_seq=table.event_seq + len(events))
    public = replace(state.public, state_version=state.public.state_version + 1)
    return replace(state, public=public, extension=new_table), events
