"""Texas public table data (P3-01, extended in P3-02), registered as a core public extension.

Everything here is public to every player. Hole cards and the undealt deck stay in
PrivateGameData. Player.points keeps the hand's starting stack (the game_players
initial_points snapshot); live chips are in SeatState.stack, so for every seat
stack + committed == Player.points until settlement (checked in check_consistency).
Every field is validated with exact types; the field matrix test enforces that.
"""

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from app.games.core.card import Card
from app.games.core.extensions import PublicExtension, register_public_extension
from app.games.core.models import GameStatus, PublicGameData
from app.games.core.validation import (
    require_bool,
    require_enum,
    require_exact_tuple,
    require_nonnegative_int,
    require_uuid,
)
from app.games.texas_holdem.positions import MAX_PLAYERS, MIN_PLAYERS

MAX_BOARD_CARDS = 5


class Street(Enum):
    PRE_FLOP = "pre_flop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"


class HandEnd(Enum):
    NONE = "none"
    LAST_STANDING = "last_standing"  # everyone else folded; no showdown
    SHOWDOWN = "showdown"  # betting is over; pots are settled elsewhere (P3-04)


BOARD_SIZE = {
    Street.PRE_FLOP: 0,
    Street.FLOP: 3,
    Street.TURN: 4,
    Street.RIVER: 5,
    Street.SHOWDOWN: 5,
}


@dataclass(frozen=True, slots=True)
class SeatState:
    seat: int
    player_id: UUID
    stack: int
    committed: int  # chips put into the pot during this hand
    all_in: bool
    folded: bool
    street_committed: int = 0  # chips put in during the current betting round
    acted: bool = False  # has acted in this round (blinds alone do not count)
    # The current bet this seat faced (or made) when it last acted this round. A seat may
    # raise again only if the bet has since grown by at least the minimum raise.
    bet_seen: int = 0
    # Chips this seat received at settlement (its refund plus its winnings); 0 before then.
    payout: int = 0

    def __post_init__(self) -> None:
        require_nonnegative_int(self.seat, "seat")
        require_uuid(self.player_id, "seat player_id")
        require_nonnegative_int(self.stack, "stack")
        require_nonnegative_int(self.committed, "committed")
        require_bool(self.all_in, "all_in")
        require_bool(self.folded, "folded")
        require_nonnegative_int(self.street_committed, "street_committed")
        require_bool(self.acted, "acted")
        require_nonnegative_int(self.bet_seen, "bet_seen")
        require_nonnegative_int(self.payout, "payout")
        if self.all_in != (self.stack == 0):
            raise ValueError("a seat is all-in exactly when it has no chips left")
        if self.all_in and self.folded:
            raise ValueError("a seat cannot be both all-in and folded")
        if self.street_committed > self.committed:
            raise ValueError("a round commitment cannot exceed the hand commitment")


@dataclass(frozen=True, slots=True)
class ShownHand:
    """A hole-card pair made public at showdown (every seat still in the hand shows)."""

    seat: int
    cards: tuple[Card, ...]

    def __post_init__(self) -> None:
        require_nonnegative_int(self.seat, "seat")
        require_exact_tuple(self.cards, Card, "cards")
        if len(self.cards) != 2 or len(set(self.cards)) != 2:
            raise ValueError("a shown hand is exactly two distinct cards")


@register_public_extension
@dataclass(frozen=True, slots=True)
class TexasPublic(PublicExtension):
    street: Street
    button_seat: int
    small_blind_seat: int
    big_blind_seat: int
    seats: tuple[SeatState, ...]
    board: tuple[Card, ...]
    pot: int
    current_bet: int  # the highest street_committed this round
    ended: HandEnd = HandEnd.NONE
    event_seq: int = 0  # the sequence number the next event will use
    min_raise: int = 1  # the smallest raise increment (the last full raise, at least the big blind)
    showdown: tuple[ShownHand, ...] = ()  # hands made public when the hand ends at a showdown
    settled: bool = False  # True once the settlement has been applied to the stacks (once only)

    def __post_init__(self) -> None:
        require_enum(self.street, Street, "street")
        require_nonnegative_int(self.button_seat, "button_seat")
        require_nonnegative_int(self.small_blind_seat, "small_blind_seat")
        require_nonnegative_int(self.big_blind_seat, "big_blind_seat")
        require_exact_tuple(self.seats, SeatState, "seats")
        require_exact_tuple(self.board, Card, "board")
        require_nonnegative_int(self.pot, "pot")
        require_nonnegative_int(self.current_bet, "current_bet")
        require_enum(self.ended, HandEnd, "ended")
        require_nonnegative_int(self.event_seq, "event_seq")
        require_nonnegative_int(self.min_raise, "min_raise")
        require_exact_tuple(self.showdown, ShownHand, "showdown")
        require_bool(self.settled, "settled")
        if self.min_raise < 1:
            raise ValueError("min_raise must be at least 1")
        numbers = [seat.seat for seat in self.seats]
        if not MIN_PLAYERS <= len(numbers) <= MAX_PLAYERS:
            raise ValueError("a table needs 2 to 9 seats")
        if numbers != sorted(set(numbers)):
            raise ValueError("seats must be unique and in increasing order")
        if len({seat.player_id for seat in self.seats}) != len(self.seats):
            raise ValueError("a player cannot occupy two seats")
        for name, number in (
            ("button", self.button_seat),
            ("small blind", self.small_blind_seat),
            ("big blind", self.big_blind_seat),
        ):
            if number not in numbers:
                raise ValueError(f"{name} seat must be an occupied seat")
        if self.small_blind_seat == self.big_blind_seat:
            raise ValueError("small and big blind cannot share a seat")
        if len(numbers) == 2 and self.small_blind_seat != self.button_seat:
            raise ValueError("heads-up, the button is the small blind")
        if self.street is Street.PRE_FLOP and self.board:
            raise ValueError("there is no board before the flop")
        if len(set(self.board)) != len(self.board):
            raise ValueError("board cards must be distinct")
        if len(self.board) != BOARD_SIZE[self.street]:
            raise ValueError("board size does not match the street")
        if self.pot != sum(seat.committed for seat in self.seats):
            raise ValueError("pot must equal the chips committed by all seats")
        if self.current_bet != max(seat.street_committed for seat in self.seats):
            raise ValueError("current_bet must equal the highest round commitment")
        if any(seat.bet_seen > self.current_bet for seat in self.seats):
            raise ValueError("a seat cannot have seen a bet higher than the current bet")
        live = sum(1 for seat in self.seats if not seat.folded)
        if (self.ended is HandEnd.SHOWDOWN) != (self.street is Street.SHOWDOWN):
            raise ValueError("showdown street and showdown ending go together")
        if self.ended is HandEnd.LAST_STANDING and live != 1:
            raise ValueError("a last-standing ending needs exactly one live seat")
        if self.ended is not HandEnd.LAST_STANDING and live < 2:
            raise ValueError("a hand with one live seat has ended")
        if self.settled and self.ended is HandEnd.NONE:
            raise ValueError("only a finished hand can be settled")
        if any(seat.folded and seat.payout for seat in self.seats):
            raise ValueError("a folded seat cannot receive chips")
        if self.settled:
            if sum(seat.payout for seat in self.seats) != self.pot:
                raise ValueError("a settled hand must pay out exactly the pot")
        elif any(seat.payout for seat in self.seats):
            raise ValueError("nothing is paid out before the settlement")
        shown = [hand.seat for hand in self.showdown]
        expected = [seat.seat for seat in self.seats if not seat.folded]
        if self.ended is HandEnd.SHOWDOWN:
            if shown != expected:
                raise ValueError("every seat still in the hand must show at a showdown")
            every = [card for hand in self.showdown for card in hand.cards] + list(self.board)
            if len(every) != len(set(every)):
                raise ValueError("shown cards must be distinct and not on the board")
        elif self.showdown:
            raise ValueError("hands are only shown at a showdown")

    def check_consistency(self, public: object) -> None:
        if type(public) is not PublicGameData:
            raise TypeError("public must be an exact PublicGameData instance")
        players = public.players
        if [(s.seat, s.player_id) for s in self.seats] != [(p.seat, p.id) for p in players]:
            raise ValueError("extension seats must match the players")
        for seat, player in zip(self.seats, players, strict=True):
            if self.settled:
                expected = player.points - seat.committed + seat.payout
                if seat.stack != expected:
                    raise ValueError(
                        "a settled stack is its starting points minus its stake plus its payout"
                    )
            elif seat.stack + seat.committed != player.points:
                raise ValueError("chips must add up to the player's starting points")
        finished = public.status is GameStatus.FINISHED
        if finished != (self.ended is not HandEnd.NONE):
            raise ValueError("the hand has ended exactly when the game is finished")
        if public.turn is not None:
            if finished:
                raise ValueError("there is no turn after the hand ends")
            holder = next((s for s in self.seats if s.player_id == public.turn.player_id), None)
            if holder is None or holder.folded or holder.all_in:
                raise ValueError("the turn must belong to a seat that can act")
