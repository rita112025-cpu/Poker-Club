"""P2-E Texas hold'em five-card hand evaluation: pure functions, no engine or storage.

Scope: exactly five cards, standard Texas ranking. Best-of-seven selection, pots,
betting, Big Two, Chinese poker and five-card draw are out of scope. Suits decide
only whether a hand is a flush; they never break ties. The royal flush is an
ace-high straight flush. A is low only in A2345 (a 5-high straight); there is no
wrap-around. Card/Rank/Suit enum order has no ranking meaning, so strengths come
from the explicit tables below.

The result reveals hand strength: server-side use only, never in public data or logs.
Runtime imports the whole app.games.core package; the static dependency is Card only.
"""

from dataclasses import dataclass
from enum import Enum

from app.games.core.card import Card, Rank

_RANK_VALUE: dict[Rank, int] = {
    Rank.TWO: 2,
    Rank.THREE: 3,
    Rank.FOUR: 4,
    Rank.FIVE: 5,
    Rank.SIX: 6,
    Rank.SEVEN: 7,
    Rank.EIGHT: 8,
    Rank.NINE: 9,
    Rank.TEN: 10,
    Rank.JACK: 11,
    Rank.QUEEN: 12,
    Rank.KING: 13,
    Rank.ACE: 14,
}
_WHEEL = (14, 5, 4, 3, 2)
HAND_SIZE = 5


class HandCategory(Enum):
    HIGH_CARD = "high_card"
    ONE_PAIR = "one_pair"
    TWO_PAIR = "two_pair"
    THREE_OF_A_KIND = "three_of_a_kind"
    STRAIGHT = "straight"
    FLUSH = "flush"
    FULL_HOUSE = "full_house"
    FOUR_OF_A_KIND = "four_of_a_kind"
    STRAIGHT_FLUSH = "straight_flush"


# Explicit strength (not declaration order) and tiebreak length per category.
_STRENGTH: dict[HandCategory, int] = {
    HandCategory.HIGH_CARD: 0,
    HandCategory.ONE_PAIR: 1,
    HandCategory.TWO_PAIR: 2,
    HandCategory.THREE_OF_A_KIND: 3,
    HandCategory.STRAIGHT: 4,
    HandCategory.FLUSH: 5,
    HandCategory.FULL_HOUSE: 6,
    HandCategory.FOUR_OF_A_KIND: 7,
    HandCategory.STRAIGHT_FLUSH: 8,
}
_TIEBREAK_LENGTH: dict[HandCategory, int] = {
    HandCategory.HIGH_CARD: 5,
    HandCategory.ONE_PAIR: 4,
    HandCategory.TWO_PAIR: 3,
    HandCategory.THREE_OF_A_KIND: 3,
    HandCategory.STRAIGHT: 1,
    HandCategory.FLUSH: 5,
    HandCategory.FULL_HOUSE: 2,
    HandCategory.FOUR_OF_A_KIND: 2,
    HandCategory.STRAIGHT_FLUSH: 1,
}


def _descending(values: tuple[int, ...]) -> bool:
    return all(earlier > later for earlier, later in zip(values, values[1:], strict=False))


def _is_straight_run(values: tuple[int, ...]) -> bool:
    return values == _WHEEL or (_descending(values) and values[0] - values[-1] == HAND_SIZE - 1)


def _is_possible(category: HandCategory, tiebreak: tuple[int, ...]) -> bool:
    """True exactly for tiebreaks an evaluated hand of this category can produce.

    Assumes every value is already an int in 2-14 of the right length.
    """
    if category in (HandCategory.STRAIGHT, HandCategory.STRAIGHT_FLUSH):
        return tiebreak[0] >= 5
    if category in (HandCategory.FOUR_OF_A_KIND, HandCategory.FULL_HOUSE):
        return tiebreak[0] != tiebreak[1]
    if category in (HandCategory.FLUSH, HandCategory.HIGH_CARD):
        return _descending(tiebreak) and not _is_straight_run(tiebreak)
    if category is HandCategory.TWO_PAIR:
        high, low, kicker = tiebreak
        return high > low and kicker not in (high, low)
    # one pair and three of a kind: a made rank followed by strictly descending kickers
    made, kickers = tiebreak[0], tiebreak[1:]
    return _descending(kickers) and made not in kickers


@dataclass(frozen=True, slots=True)
class HandRank:
    """Category plus tiebreak values (2-14, strongest first, never suits).

    Wheel straights use 5 as their only tiebreak value. Construction also rejects
    tiebreaks no real hand of that category can have (for example a 2-high straight
    or a full house of one rank), so an externally built HandRank is still plausible.
    """

    category: HandCategory
    tiebreak: tuple[int, ...]

    def __post_init__(self) -> None:
        if type(self.category) is not HandCategory:
            raise TypeError("category must be a HandCategory member")
        if type(self.tiebreak) is not tuple:
            raise TypeError("tiebreak must be a tuple")
        if any(type(value) is not int for value in self.tiebreak):
            raise TypeError("tiebreak values must be integers")
        if any(not 2 <= value <= 14 for value in self.tiebreak):
            raise ValueError("tiebreak values must be between 2 and 14")
        if len(self.tiebreak) != _TIEBREAK_LENGTH[self.category]:
            raise ValueError("tiebreak length does not match the category")
        if not _is_possible(self.category, self.tiebreak):
            raise ValueError("tiebreak is impossible for this category")

    @property
    def sort_key(self) -> tuple[int, tuple[int, ...]]:
        return (_STRENGTH[self.category], self.tiebreak)


def _validate(cards: object) -> tuple[Card, ...]:
    if type(cards) is not tuple:
        raise TypeError("cards must be a tuple")
    if len(cards) != HAND_SIZE:
        raise ValueError(f"a hand must contain exactly {HAND_SIZE} cards")
    for card in cards:
        if type(card) is not Card:
            raise TypeError("cards must contain only exact Card instances")
    if len(set(cards)) != HAND_SIZE:
        raise ValueError("a hand cannot contain duplicate cards")
    return cards


def evaluate_five(cards: tuple[Card, ...]) -> HandRank:
    """Rank exactly five distinct cards; invalid input raises (a programming error)."""
    hand = _validate(cards)
    values = sorted((_RANK_VALUE[card.rank] for card in hand), reverse=True)
    is_flush = len({card.suit for card in hand}) == 1

    straight_high = 0
    if len(set(values)) == HAND_SIZE:
        if values[0] - values[4] == 4:
            straight_high = values[0]
        elif tuple(values) == _WHEEL:
            straight_high = 5

    if straight_high and is_flush:
        return HandRank(HandCategory.STRAIGHT_FLUSH, (straight_high,))

    counts: dict[int, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    # Group by (multiplicity, value), strongest first.
    groups = sorted(((count, value) for value, count in counts.items()), reverse=True)
    shape = tuple(count for count, _ in groups)
    ordered = tuple(value for _, value in groups)

    if shape == (4, 1):
        return HandRank(HandCategory.FOUR_OF_A_KIND, ordered)
    if shape == (3, 2):
        return HandRank(HandCategory.FULL_HOUSE, ordered)
    if is_flush:
        return HandRank(HandCategory.FLUSH, ordered)
    if straight_high:
        return HandRank(HandCategory.STRAIGHT, (straight_high,))
    if shape == (3, 1, 1):
        return HandRank(HandCategory.THREE_OF_A_KIND, ordered)
    if shape == (2, 2, 1):
        return HandRank(HandCategory.TWO_PAIR, ordered)
    if shape == (2, 1, 1, 1):
        return HandRank(HandCategory.ONE_PAIR, ordered)
    return HandRank(HandCategory.HIGH_CARD, ordered)


def compare(first: HandRank, second: HandRank) -> int:
    """-1 if first is weaker, 1 if stronger, 0 for a tie (split-pot handling is elsewhere)."""
    if type(first) is not HandRank or type(second) is not HandRank:
        raise TypeError("compare requires exact HandRank instances")
    if first.sort_key < second.sort_key:
        return -1
    if first.sort_key > second.sort_key:
        return 1
    return 0
