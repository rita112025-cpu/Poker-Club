"""Texas public table data (P3-01), registered as a core public extension.

Everything here is public to every player. Hole cards and the undealt deck stay in
PrivateGameData. Player.points keeps the hand's starting stack (the game_players
initial_points snapshot); live chips are in SeatState.stack. Every field is validated with
exact types; the field matrix test enforces that for each registered extension.
"""

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from app.games.core.card import Card
from app.games.core.extensions import PublicExtension, register_public_extension
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


@dataclass(frozen=True, slots=True)
class SeatState:
    seat: int
    player_id: UUID
    stack: int
    committed: int  # chips put into the pot during this hand
    all_in: bool
    folded: bool

    def __post_init__(self) -> None:
        require_nonnegative_int(self.seat, "seat")
        require_uuid(self.player_id, "seat player_id")
        require_nonnegative_int(self.stack, "stack")
        require_nonnegative_int(self.committed, "committed")
        require_bool(self.all_in, "all_in")
        require_bool(self.folded, "folded")
        if self.all_in and self.stack != 0:
            raise ValueError("an all-in seat has no chips left")
        if self.all_in and self.folded:
            raise ValueError("a seat cannot be both all-in and folded")


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
    current_bet: int

    def __post_init__(self) -> None:
        require_enum(self.street, Street, "street")
        require_nonnegative_int(self.button_seat, "button_seat")
        require_nonnegative_int(self.small_blind_seat, "small_blind_seat")
        require_nonnegative_int(self.big_blind_seat, "big_blind_seat")
        require_exact_tuple(self.seats, SeatState, "seats")
        require_exact_tuple(self.board, Card, "board")
        require_nonnegative_int(self.pot, "pot")
        require_nonnegative_int(self.current_bet, "current_bet")
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
        if len(self.board) > MAX_BOARD_CARDS or len(set(self.board)) != len(self.board):
            raise ValueError("board must have at most 5 distinct cards")
        if self.street is Street.PRE_FLOP and self.board:
            raise ValueError("there is no board before the flop")
        if self.pot != sum(seat.committed for seat in self.seats):
            raise ValueError("pot must equal the chips committed by all seats")
