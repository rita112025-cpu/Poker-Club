"""Street machine, legal actions and no-limit raising rules for a Texas hand (P3-02/P3-03).

Amounts for bet and raise are "raise-to": the seat's TOTAL commitment this betting round.
The minimum bet is the big blind. The minimum raise increment is the size of the last full
raise (at least the big blind) and resets to the big blind every street. A bet or raise
(including an all-in that exceeds the call amount) is "full" when its increment is at least
the minimum raise increment; a smaller all-in is a short raise: it raises the amount to call
but changes neither the minimum increment nor who may raise.
Re-opening: each seat remembers the current bet it last faced (bet_seen). It may raise again
only if the bet has grown by at least the minimum increment since then, so one short all-in
does not re-open the betting but several short all-ins that add up to a full raise do.
There is no maximum except the seat's stack. Before the flop, if the big blind posted less
than the big blind, the minimum raise-to is still the big blind plus the minimum increment.

A betting round is complete when every live seat that can still act has acted and matched
the current bet. The big blind keeps its option before the flop. With fewer than two seats
able to act there is no betting: remaining streets are dealt out (also when the round is
already complete at the start of the hand). Folding is always allowed, even when a check is
possible. A seat whose opponents are all all-in (or folded) cannot bet or raise.
Burning is controlled by the rules.
"""

from dataclasses import dataclass, replace

from app.games.core.card import Card
from app.games.core.extensions import EventPayload
from app.games.core.models import GameState, GameStatus, Turn
from app.games.texas_holdem.events import HandEnded, StreetDealt
from app.games.texas_holdem.positions import next_seat
from app.games.texas_holdem.state import HandEnd, SeatState, ShownHand, Street, TexasPublic

FOLD = "fold"
CHECK = "check"
CALL = "call"
ALL_IN = "all_in"
BET = "bet"
RAISE = "raise"
KNOWN_ACTIONS = (FOLD, CHECK, CALL, ALL_IN, BET, RAISE)

_STREET_AFTER = {
    Street.PRE_FLOP: Street.FLOP,
    Street.FLOP: Street.TURN,
    Street.TURN: Street.RIVER,
}


@dataclass(frozen=True, slots=True)
class LegalActions:
    kinds: tuple[str, ...]
    to_call: int
    # Inclusive raise-to range for bet/raise; None when neither is available.
    min_to: int | None = None
    max_to: int | None = None


def can_act(seat: SeatState) -> bool:
    return not seat.folded and not seat.all_in


def amount_to_call(ext: TexasPublic, seat: SeatState) -> int:
    return ext.current_bet - seat.street_committed


def seat_to_act(state: GameState) -> SeatState | None:
    ext = state.extension
    turn = state.public.turn
    if not isinstance(ext, TexasPublic) or turn is None:
        return None
    return next((s for s in ext.seats if s.player_id == turn.player_id), None)


def stack_total(seat: SeatState) -> int:
    """The most this seat can have committed this round (its all-in total)."""
    return seat.stack + seat.street_committed


def can_raise(ext: TexasPublic, seat: SeatState) -> bool:
    """Whether the bet is open to this seat: it has not acted, or the bet has grown by a
    full minimum raise since it last acted."""
    return not seat.acted or ext.current_bet - seat.bet_seen >= ext.min_raise


def minimum_raise_to(ext: TexasPublic) -> int:
    base = ext.current_bet
    if ext.street is Street.PRE_FLOP:
        base = max(base, ext.min_raise)  # min_raise is the big blind until a full raise
    return base + ext.min_raise


def legal_actions(state: GameState) -> LegalActions | None:
    """What the player to act may do now (None when nobody is to act)."""
    ext = state.extension
    seat = seat_to_act(state)
    if (
        not isinstance(ext, TexasPublic)
        or seat is None
        or state.public.status is not GameStatus.IN_PROGRESS
    ):
        return None
    owed = amount_to_call(ext, seat)
    total = stack_total(seat)
    kinds = [FOLD, CHECK if owed == 0 else CALL]
    low: int | None = None
    high: int | None = None
    opponents_can_act = any(can_act(s) for s in ext.seats if s.seat != seat.seat)
    if total > ext.current_bet and can_raise(ext, seat) and opponents_can_act:
        kinds.append(ALL_IN)  # an all-in that exceeds the call amount is a raise
        needed = minimum_raise_to(ext)
        if total >= needed:
            kinds.append(BET if ext.current_bet == 0 else RAISE)
            low, high = needed, total
    elif owed > 0 and seat.stack <= owed:
        kinds.append(ALL_IN)  # a short call
    # With every opponent all-in or folded there is nobody to raise against: only call or fold.
    return LegalActions(tuple(kinds), owed, low, high)


def _needs_action(ext: TexasPublic, seat: SeatState) -> bool:
    return not seat.acted or seat.street_committed < ext.current_bet


def _clockwise_from(ext: TexasPublic, seat_number: int | None) -> list[SeatState]:
    """Seats in clockwise order starting just after seat_number (the button if None)."""
    numbers = tuple(s.seat for s in ext.seats)
    start = ext.button_seat if seat_number is None else seat_number
    by_number = {s.seat: s for s in ext.seats}
    order = []
    current = start
    for _ in range(len(numbers)):
        current = next_seat(numbers, current)
        order.append(by_number[current])
    return order


def round_is_complete(ext: TexasPublic) -> bool:
    """True when the current betting round needs no further action."""
    live = [s for s in ext.seats if not s.folded]
    able = [s for s in live if not s.all_in]
    return (
        not able
        or not any(_needs_action(ext, s) for s in able)
        or (len(able) == 1 and able[0].street_committed >= ext.current_bet)
    )


def _deal_next_street(
    ext: TexasPublic, remaining: tuple[Card, ...], burn: bool, big_blind: int
) -> tuple[TexasPublic, tuple[Card, ...], tuple[Card, ...]]:
    street = _STREET_AFTER[ext.street]
    skip = 1 if burn else 0
    count = 3 if street is Street.FLOP else 1
    if len(remaining) < skip + count:
        raise ValueError("not enough cards left to deal the street")
    cards = remaining[skip : skip + count]
    fresh = tuple(replace(s, street_committed=0, acted=False, bet_seen=0) for s in ext.seats)
    updated = replace(
        ext,
        street=street,
        board=ext.board + cards,
        seats=fresh,
        current_bet=0,
        min_raise=big_blind,
    )
    return updated, remaining[skip + count :], cards


def _shown_hands(state: GameState, ext: TexasPublic) -> tuple[ShownHand, ...]:
    """The hole cards of every seat still in the hand (the showdown reveal)."""
    hands = {item.player_id: item.hand for item in state.private.players}
    return tuple(
        ShownHand(seat.seat, hands[seat.player_id]) for seat in ext.seats if not seat.folded
    )


def advance(
    state: GameState,
    ext: TexasPublic,
    burn: bool,
    big_blind: int,
    actor_seat: int | None,
    payloads: list[EventPayload],
) -> tuple[GameState, list[EventPayload]]:
    """Move the hand forward after an action (or at creation when nobody can act).

    `ext` is the table data after the action itself (it may already say the hand ended);
    `state` supplies the core data and the undealt cards. Returns the next state
    (state_version + 1, event_seq advanced by the number of events) and the full list of
    event payloads, in order. `payloads` already holds the event for the action itself.
    """
    remaining = state.private.remaining_cards
    status = GameStatus.IN_PROGRESS
    turn_player = None
    events = list(payloads)
    while True:
        live = [s for s in ext.seats if not s.folded]
        if len(live) == 1:
            ext = replace(ext, ended=HandEnd.LAST_STANDING)
            events.append(HandEnded(HandEnd.LAST_STANDING))
            status = GameStatus.FINISHED
            break
        able = [s for s in live if not s.all_in]
        if not round_is_complete(ext):
            chosen = next(
                s for s in _clockwise_from(ext, actor_seat) if can_act(s) and _needs_action(ext, s)
            )
            turn_player = chosen.player_id
            break
        if ext.street is Street.RIVER:
            ext = replace(
                ext,
                street=Street.SHOWDOWN,
                ended=HandEnd.SHOWDOWN,
                showdown=_shown_hands(state, ext),
            )
            events.append(HandEnded(HandEnd.SHOWDOWN))
            status = GameStatus.FINISHED
            break
        ext, remaining, cards = _deal_next_street(ext, remaining, burn, big_blind)
        events.append(StreetDealt(ext.street, cards))
        actor_seat = None
        if len(able) >= 2:
            first = next(s for s in _clockwise_from(ext, None) if can_act(s))
            turn_player = first.player_id
            break
    ext = replace(ext, event_seq=ext.event_seq + len(events))
    public = replace(
        state.public,
        state_version=state.public.state_version + 1,
        status=status,
        turn=None if turn_player is None else Turn(turn_player),
    )
    private = replace(state.private, remaining_cards=remaining)
    return replace(state, public=public, private=private, extension=ext), events
