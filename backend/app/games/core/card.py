"""Standard playing cards. Enum declaration order has no game ranking meaning."""

from dataclasses import dataclass
from enum import Enum


class Suit(Enum):
    CLUBS = "C"
    DIAMONDS = "D"
    HEARTS = "H"
    SPADES = "S"


class Rank(Enum):
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"


@dataclass(frozen=True, slots=True)
class Card:
    """Immutable, hashable card; comparing game strength belongs to each engine."""

    rank: Rank
    suit: Suit

    def __post_init__(self) -> None:
        if not isinstance(self.rank, Rank):
            raise TypeError("rank must be a Rank member")
        if not isinstance(self.suit, Suit):
            raise TypeError("suit must be a Suit member")

    @property
    def code(self) -> str:
        """Canonical server-side serialization, e.g. AS or 10H."""
        return self.rank.value + self.suit.value

    @classmethod
    def from_code(cls, code: str) -> "Card":
        """Parse exact uppercase codes, without coercion, aliases or whitespace."""
        if not isinstance(code, str):
            raise TypeError("card code must be a string")
        if len(code) not in (2, 3):
            raise ValueError("Invalid card code")
        try:
            return cls(rank=Rank(code[:-1]), suit=Suit(code[-1]))
        except ValueError:
            raise ValueError("Invalid card code") from None
