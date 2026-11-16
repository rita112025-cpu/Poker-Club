"""Street machine and legal actions for a Texas hand (P3-02). Pure functions.

Scope: fold, check, call and the short all-in (an all-in that does not exceed the call
amount, which behaves exactly like a call). bet, raise and an all-in that exceeds the call
amount need the minimum-raise and re-opening rules of P3-03, so they are recognised and
rejected with NOT_SUPPORTED_YET instead of guessing a rule.

A betting round is complete when every live seat that can still act has acted and has
matched the current bet. The big blind therefore keeps its option before the flop. With
fewer than two seats able to act there is no betting: remaining streets are dealt out.
Folding is always allowed, even when a check is possible. Burning is controlled by the
rules (one card before the flop, turn and river).
"""

from dataclasses import dataclass, replace

from app.games.core.card import Card
from app.games.core.extensions import EventPayload
from app.games.core.models import GameState, GameStatus, Turn
from app.games.texas_holdem.events import HandEnded, StreetDealt
from app.games.texas_holdem.positions import next_seat
from app.games.texas_holdem.state import HandEnd, SeatState, Street, TexasPublic

FOLD = "fold"
CHECK = "check"
CALL = "call"
ALL_IN = "all_in"
BET = "bet"
RAISE = "raise"
KNOWN_ACTIONS = (FOLD, CHECK, CALL, ALL_IN, BET, RAISE)
UNSUPPORTED_ACTIONS = (BET, RAISE)

_STREET_AFTER = {
    Street.PRE_FLOP: Street.FLOP,
    Street.FLOP: Street.TURN,
    Street.TURN: Street.RIVER,
}


@dataclass(frozen=True, slots=True)
class LegalActions:
    kinds: tuple[str, ...]
    to_call: int


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
    kinds = [FOLD, CHECK if owed == 0 else CALL]
    if owed > 0 and seat.stack <= owed:
        kinds.append(ALL_IN)
    return LegalActions(tuple(kinds), owed)


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


def _deal_next_street(
    ext: TexasPublic, remaining: tuple[Card, ...], burn: bool
) -> tuple[TexasPublic, tuple[Card, ...], tuple[Card, ...]]:
    street = _STREET_AFTER[ext.street]
    skip = 1 if burn else 0
    count = 3 if street is Street.FLOP else 1
    if len(remaining) < skip + count:
        raise ValueError("not enough cards left to deal the street")
    cards = remaining[skip : skip + count]
    fresh = tuple(replace(s, street_committed=0, acted=False) for s in ext.seats)
    updated = replace(ext, street=street, board=ext.board + cards, seats=fresh, current_bet=0)
    return updated, remaining[skip + count :], cards


def advance(
    state: GameState,
    ext: TexasPublic,
    burn: bool,
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
        complete = (
            not able
            or not any(_needs_action(ext, s) for s in able)
            or (len(able) == 1 and able[0].street_committed >= ext.current_bet)
        )
        if not complete:
            chosen = next(
                s for s in _clockwise_from(ext, actor_seat) if can_act(s) and _needs_action(ext, s)
            )
            turn_player = chosen.player_id
            break
        if ext.street is Street.RIVER:
            ext = replace(ext, street=Street.SHOWDOWN, ended=HandEnd.SHOWDOWN)
            events.append(HandEnded(HandEnd.SHOWDOWN))
            status = GameStatus.FINISHED
            break
        ext, remaining, cards = _deal_next_street(ext, remaining, burn)
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
