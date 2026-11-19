from collections import Counter
from dataclasses import dataclass
from enum import IntEnum

from app.games.big_two.config import STRAIGHTS, card_key
from app.games.core.card import Card


class Category(IntEnum):
    SINGLE = 0
    PAIR = 1
    TRIPLE = 2
    STRAIGHT = 3
    FLUSH = 4
    FULL_HOUSE = 5
    QUADS = 6
    STRAIGHT_FLUSH = 7


@dataclass(frozen=True, slots=True)
class Combination:
    size: int
    category: Category
    key: tuple[int, ...]

    def beats(self, other: "Combination") -> bool:
        return self.size == other.size and (self.category, self.key) > (other.category, other.key)


def classify(cards: tuple[Card, ...]) -> Combination | None:
    size = len(cards)
    if size not in (1, 2, 3, 5) or len(set(cards)) != size:
        return None
    ordered = sorted(map(card_key, cards))
    ranks = tuple(rank for rank, _ in ordered)
    highest_rank, highest_suit = ordered[-1]
    counts = Counter(ranks)
    if size < 5:
        if len(counts) != 1:
            return None
        category = (Category.SINGLE, Category.PAIR, Category.TRIPLE)[size - 1]
        key = (highest_rank, highest_suit) if size < 3 else (highest_rank,)
        return Combination(size, category, key)

    flush = len({card.suit for card in cards}) == 1
    if ranks in STRAIGHTS:
        category = Category.STRAIGHT_FLUSH if flush else Category.STRAIGHT
        return Combination(size, category, (STRAIGHTS.index(ranks), highest_suit))
    if flush:
        return Combination(size, Category.FLUSH, (*reversed(ranks), highest_suit))
    rank, count = counts.most_common(1)[0]
    if count == 4:
        return Combination(size, Category.QUADS, (rank,))
    if count == 3 and len(counts) == 2:
        return Combination(size, Category.FULL_HOUSE, (rank,))
    return None
