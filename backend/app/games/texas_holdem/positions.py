"""Seat order, button, blinds and first actor (P3-01). Pure functions on seat numbers.

Seat numbers increase clockwise; the seat after the highest wraps to the lowest, and
seat numbers may have gaps. The first hand's button is the lowest seat; later hands
rotate with next_button. Heads-up: the button is the small blind and acts first before the
flop. With three or more players the small blind is left of the button, the big blind left of
the small blind and the first actor left of the big blind. Dead-button handling for
eliminated players is out of scope (single hand).
"""

from dataclasses import dataclass

MIN_PLAYERS = 2
MAX_PLAYERS = 9


@dataclass(frozen=True, slots=True)
class Positions:
    button: int
    small_blind: int
    big_blind: int
    first_to_act: int


def validate_seats(seats: object) -> tuple[int, ...]:
    """Exact tuple of 2-9 distinct non-negative int seat numbers; returns them sorted."""
    if type(seats) is not tuple:
        raise TypeError("seats must be a tuple")
    if any(type(seat) is not int for seat in seats):
        raise TypeError("seats must contain only integers")
    if any(seat < 0 for seat in seats):
        raise ValueError("seat numbers cannot be negative")
    if len(set(seats)) != len(seats):
        raise ValueError("seats cannot repeat")
    if not MIN_PLAYERS <= len(seats) <= MAX_PLAYERS:
        raise ValueError(f"a hand needs {MIN_PLAYERS} to {MAX_PLAYERS} seats")
    return tuple(sorted(seats))


def next_seat(seats: tuple[int, ...], seat: int) -> int:
    """The next seat clockwise, wrapping from the highest to the lowest."""
    ordered = validate_seats(seats)
    if type(seat) is not int or seat not in ordered:
        raise ValueError("seat must be one of the seats")
    for candidate in ordered:
        if candidate > seat:
            return candidate
    return ordered[0]


def initial_button(seats: tuple[int, ...]) -> int:
    return validate_seats(seats)[0]


def next_button(seats: tuple[int, ...], button: int) -> int:
    """Button for the following hand when every seat stays occupied."""
    return next_seat(seats, button)


def positions(seats: tuple[int, ...], button: int) -> Positions:
    ordered = validate_seats(seats)
    if type(button) is not int or button not in ordered:
        raise ValueError("button must be one of the seats")
    if len(ordered) == 2:
        other = next_seat(ordered, button)
        return Positions(button, button, other, button)
    small = next_seat(ordered, button)
    big = next_seat(ordered, small)
    return Positions(button, small, big, next_seat(ordered, big))
