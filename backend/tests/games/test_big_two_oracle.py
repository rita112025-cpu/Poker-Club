"""Independent oracle for the D1 hand ranking (R02-R10).

The oracle below is written from the contract text only and shares no code or constants with
`app.games.big_two`. It is checked against `classify` / `Combination.beats` by exhaustive
enumeration where the space is small and by seeded sampling elsewhere. A one-off run over all
2,598,960 five-card hands and 300,000 random comparisons also had zero disagreements; that
full run is intentionally not part of the regular suite because of its running time.
"""

import itertools
import random
from collections import Counter

from app.games.big_two.hands import Category, classify
from app.games.core.card import Card

RANK_ORDER = "3 4 5 6 7 8 9 10 J Q K A 2".split()
SUIT_ORDER = "CDHS"  # R02: clubs < diamonds < hearts < spades
STRAIGHT_STARTS = range(8)  # R05: 34567 ... 10JQKA, never wrapping through the 2
DECK = [Card.from_code(rank + suit) for rank in RANK_ORDER for suit in SUIT_ORDER]

type Strength = tuple[int, int, tuple[int, ...]]


def rank_of(card: Card) -> int:
    return RANK_ORDER.index(card.rank.value)


def suit_of(card: Card) -> int:
    return SUIT_ORDER.index(card.suit.value)


def oracle(cards: tuple[Card, ...]) -> Strength | None:
    """(size, category, key) per R04-R10, or None when the cards are not a legal combination."""
    size = len(cards)
    ranks = sorted(rank_of(card) for card in cards)
    counts = Counter(ranks)
    top = max(cards, key=lambda card: (rank_of(card), suit_of(card)))
    if len(set(cards)) != size:
        return None
    if size in (1, 2, 3):
        if len(counts) != 1:
            return None
        key = (ranks[0], suit_of(top)) if size < 3 else (ranks[0],)
        return size, 0, key
    if size != 5:
        return None
    flush = len({suit_of(card) for card in cards}) == 1
    for start in STRAIGHT_STARTS:
        if ranks == list(range(start, start + 5)):
            return 5, 7 if flush else 3, (start, suit_of(top))
    if flush:
        return 5, 4, (*sorted(ranks, reverse=True), suit_of(top))
    if sorted(counts.values()) == [2, 3]:
        return 5, 5, (max(counts, key=lambda rank: counts[rank]),)
    if sorted(counts.values()) == [1, 4]:
        return 5, 6, (max(counts, key=lambda rank: counts[rank]),)
    return None


def agrees(cards: tuple[Card, ...]) -> bool:
    expected, actual = oracle(cards), classify(cards)
    if expected is None or actual is None:
        return expected is None and actual is None
    if expected[0] < 5:  # single / pair / triple are fully identified by their size
        return actual.size == expected[0]
    return (actual.size, int(actual.category)) == expected[:2]


def test_every_one_to_three_card_selection_matches_the_oracle() -> None:
    for size in (1, 2, 3):
        for cards in itertools.combinations(DECK, size):
            assert agrees(cards), cards


def test_exhaustive_straight_flush_straight_flush_and_set_categories() -> None:
    straights = Counter[Category]()
    for start in STRAIGHT_STARTS:
        ranks = RANK_ORDER[start : start + 5]
        for suits in itertools.product(SUIT_ORDER, repeat=5):
            cards = tuple(Card.from_code(r + s) for r, s in zip(ranks, suits, strict=True))
            assert agrees(cards), cards
            hand = classify(cards)
            assert hand is not None
            straights[hand.category] += 1
    assert straights == {Category.STRAIGHT: 8160, Category.STRAIGHT_FLUSH: 32}

    flushes = Counter[Category]()
    for suit in SUIT_ORDER:
        for chosen in itertools.combinations(RANK_ORDER, 5):
            cards = tuple(Card.from_code(rank + suit) for rank in chosen)
            assert agrees(cards), cards
            hand = classify(cards)
            assert hand is not None
            flushes[hand.category] += 1
    assert flushes == {Category.FLUSH: 5116, Category.STRAIGHT_FLUSH: 32}

    full_houses = quads = 0
    for triple, pair in itertools.permutations(RANK_ORDER, 2):
        for triple_suits in itertools.combinations(SUIT_ORDER, 3):
            for pair_suits in itertools.combinations(SUIT_ORDER, 2):
                cards = tuple(
                    Card.from_code(rank + suit)
                    for rank, suits in ((triple, triple_suits), (pair, pair_suits))
                    for suit in suits
                )
                hand = classify(cards)
                assert hand is not None and hand.category == Category.FULL_HOUSE
                assert agrees(cards)
                full_houses += 1
    for four, kicker in itertools.permutations(RANK_ORDER, 2):
        for kicker_suit in SUIT_ORDER:
            cards = tuple(Card.from_code(four + suit) for suit in SUIT_ORDER) + (
                Card.from_code(kicker + kicker_suit),
            )
            hand = classify(cards)
            assert hand is not None and hand.category == Category.QUADS
            assert agrees(cards)
            quads += 1
    assert (full_houses, quads) == (3744, 624)


def test_sampled_five_card_selections_match_the_oracle() -> None:
    generator = random.Random(20261119)
    for _ in range(20000):
        assert agrees(tuple(generator.sample(DECK, 5)))


def sample_legal(generator: random.Random, size: int) -> tuple[Card, ...]:
    while True:
        shape = generator.random()
        if size == 5 and shape < 0.25:
            start = generator.randrange(8)
            cards = tuple(
                Card.from_code(RANK_ORDER[start + i] + generator.choice(SUIT_ORDER))
                for i in range(5)
            )
        elif size == 5 and shape < 0.5:
            suit = generator.choice(SUIT_ORDER)
            cards = tuple(Card.from_code(rank + suit) for rank in generator.sample(RANK_ORDER, 5))
        elif size == 5 and shape < 0.75:
            triple, pair = generator.sample(RANK_ORDER, 2)
            cards = tuple(
                Card.from_code(rank + suit)
                for rank, count in ((triple, 3), (pair, 2))
                for suit in generator.sample(SUIT_ORDER, count)
            )
        elif size == 5:
            four, kicker = generator.sample(RANK_ORDER, 2)
            cards = tuple(Card.from_code(four + suit) for suit in SUIT_ORDER) + (
                Card.from_code(kicker + generator.choice(SUIT_ORDER)),
            )
        else:
            rank = generator.choice(RANK_ORDER)
            cards = tuple(
                Card.from_code(rank + suit) for suit in generator.sample(SUIT_ORDER, size)
            )
        if oracle(cards) is not None:
            return cards


def test_sampled_comparisons_match_the_oracle() -> None:
    generator = random.Random(20261120)
    for _ in range(30000):
        size = generator.choice((1, 2, 3, 5))
        left, right = sample_legal(generator, size), sample_legal(generator, size)
        left_strength, right_strength = oracle(left), oracle(right)
        left_hand, right_hand = classify(left), classify(right)
        assert left_strength is not None and right_strength is not None
        assert left_hand is not None and right_hand is not None
        assert left_hand.beats(right_hand) == (left_strength > right_strength), (left, right)
        assert right_hand.beats(left_hand) == (right_strength > left_strength), (left, right)
