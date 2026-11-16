"""Public event payloads for a Texas hand (P3-02). All events are PUBLIC; the cards named
by StreetDealt are the ones just placed on the public board, never hole cards or the deck.
"""

from dataclasses import dataclass

from app.games.core.card import Card
from app.games.core.extensions import EventPayload, register_event_payload
from app.games.core.validation import (
    require_enum,
    require_exact_tuple,
    require_nonnegative_int,
    require_text,
)
from app.games.texas_holdem.state import HandEnd, Street


@register_event_payload
@dataclass(frozen=True, slots=True)
class ActionTaken(EventPayload):
    seat: int
    action: str
    amount: int  # chips paid by this action (0 for fold and check)

    def __post_init__(self) -> None:
        require_nonnegative_int(self.seat, "seat")
        require_text(self.action, "action")
        require_nonnegative_int(self.amount, "amount")


@register_event_payload
@dataclass(frozen=True, slots=True)
class StreetDealt(EventPayload):
    street: Street
    cards: tuple[Card, ...]

    def __post_init__(self) -> None:
        require_enum(self.street, Street, "street")
        require_exact_tuple(self.cards, Card, "cards")
        if self.street in (Street.PRE_FLOP, Street.SHOWDOWN):
            raise ValueError("no cards are dealt for this street")
        if len(self.cards) != (3 if self.street is Street.FLOP else 1):
            raise ValueError("wrong number of cards for the street")
        if len(set(self.cards)) != len(self.cards):
            raise ValueError("dealt cards must be distinct")


@register_event_payload
@dataclass(frozen=True, slots=True)
class HandEnded(EventPayload):
    reason: HandEnd

    def __post_init__(self) -> None:
        require_enum(self.reason, HandEnd, "reason")
        if self.reason is HandEnd.NONE:
            raise ValueError("an ended hand needs a reason")
