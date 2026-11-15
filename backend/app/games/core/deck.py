"""Secure default decks and explicit fixed-order fixtures. Never logs card order."""

from collections.abc import Iterable
from secrets import SystemRandom

from app.games.core.card import Card, Rank, Suit


class InsufficientCardsError(ValueError):
    """A deal would exceed the remaining cards; the deck is left unchanged."""


class Deck:
    """Mutable server-owned deck. Instances must not be shared between games.

    Deck() always builds and securely shuffles 52 cards. reset() restores all
    initial cards and securely shuffles production decks again. shuffle() acts
    only on the remaining cards, never returning cards already dealt.

    Fixed-order injection is deliberately confined to for_testing(); its marker
    survives reset and shuffle. Future production engines must reject those
    marked instances. There is no seed, RNG or unshuffled-production option.
    """

    __slots__ = ("_cards", "_initial_cards", "_test_only")

    def __init__(self) -> None:
        self._initial_cards = tuple(Card(rank, suit) for suit in Suit for rank in Rank)
        self._test_only = False
        self.reset()

    @classmethod
    def for_testing(cls, cards: Iterable[Card]) -> "Deck":
        """Inject an exact deal order, including partial/empty decks, for tests only."""
        initial_cards = tuple(cards)
        if any(not isinstance(card, Card) for card in initial_cards):
            raise TypeError("test deck must contain only Card instances")
        if len(set(initial_cards)) != len(initial_cards):
            raise ValueError("Duplicate cards are not allowed")
        deck = cls.__new__(cls)
        deck._initial_cards = initial_cards
        deck._test_only = True
        deck.reset()
        return deck

    @property
    def remaining_count(self) -> int:
        return len(self._cards)

    @property
    def is_test_only(self) -> bool:
        return self._test_only

    def deal(self, count: int = 1) -> tuple[Card, ...]:
        """Deal from the front, atomically; zero is allowed, bool is not an int here."""
        if type(count) is not int:
            raise TypeError("deal count must be an integer")
        if count < 0:
            raise ValueError("deal count cannot be negative")
        if count > self.remaining_count:
            raise InsufficientCardsError("Not enough cards remaining")
        dealt = tuple(self._cards[:count])
        del self._cards[:count]
        return dealt

    def shuffle(self) -> None:
        """OS-backed cryptographic randomness; no caller-supplied RNG or seed."""
        SystemRandom().shuffle(self._cards)

    def reset(self) -> None:
        """Start a new deck cycle; fixtures repeat their explicitly supplied order."""
        self._cards = list(self._initial_cards)
        if not self._test_only:
            self.shuffle()

    def __repr__(self) -> str:
        return f"Deck(remaining_count={self.remaining_count}, is_test_only={self.is_test_only})"
