"""P3-04: best five of seven cards (best_of_seven).

Expected values are worked out by hand or come from an independent evaluator written by a
separate agent with a different algorithm (counting ranks and suits; it never scores
five-card subsets). Not applicable: settlement and betting (other test modules).
"""

import itertools
import random
from typing import Any, cast

import pytest
from seven_card_reference_independent import evaluate7

from app.games.core import Card, Rank, Suit
from app.games.texas_holdem import HandCategory, best_of_seven, evaluate_five

DECK = [Card(rank, suit) for rank in Rank for suit in Suit]


class CardWithSecret(Card):
    pass


def seven(codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes.split())


def engine_key(cards: tuple[Card, ...]) -> tuple[int, tuple[int, ...]]:
    return best_of_seven(cards).sort_key


def reference_key(cards: tuple[Card, ...]) -> tuple[int, tuple[int, ...]]:
    category, tiebreak = evaluate7([card.code for card in cards])
    return category, tuple(tiebreak)


# ---- hand-worked cases (category, tiebreak) -------------------------------------------------

CASES = [
    ("AS KS QS JS 10S 2C 3D", HandCategory.STRAIGHT_FLUSH, (14,)),  # the board is a royal flush
    ("AS 2S 3S 4S 5S 6S KD", HandCategory.STRAIGHT_FLUSH, (6,)),  # six suited in a row: 6-high
    ("AD 2D 3D 4D 5D KC 9H", HandCategory.STRAIGHT_FLUSH, (5,)),  # wheel flush
    ("9H 9D 9S 9C KD KS 2C", HandCategory.FOUR_OF_A_KIND, (9, 13)),  # quads, a pair as kicker pool
    ("9H 9D 9S 9C 8D 8S 8C", HandCategory.FOUR_OF_A_KIND, (9, 8)),  # quads plus trips: kicker 8
    ("KH KD KS 4C 4D 4S 2C", HandCategory.FULL_HOUSE, (13, 4)),  # two trips: lower trips pair up
    ("KH KD KS 4C 4D 2S 2C", HandCategory.FULL_HOUSE, (13, 4)),  # trips + two pairs: higher pair
    ("AH 9H 7H 4H 2H KS QD", HandCategory.FLUSH, (14, 9, 7, 4, 2)),
    ("AH KH 9H 7H 4H 2H QS", HandCategory.FLUSH, (14, 13, 9, 7, 4)),  # six suited: top five
    ("AH KH QH JH 9H 7H 2H", HandCategory.FLUSH, (14, 13, 12, 11, 9)),  # not a straight flush
    ("AS 2D 3H 4C 5S KD 9H", HandCategory.STRAIGHT, (5,)),  # wheel
    ("AS 2D 3H 4C 5S 6D 9H", HandCategory.STRAIGHT, (6,)),  # 6-high beats the wheel
    ("9S 8D 7H 6C 5S 4D 3H", HandCategory.STRAIGHT, (9,)),  # seven in a row: the top five
    ("QS KD AH 2C 3S 9D 7H", HandCategory.HIGH_CARD, (14, 13, 12, 9, 7)),  # no wrap-around
    ("7S 7D 7H KC 9S 4D 2H", HandCategory.THREE_OF_A_KIND, (7, 13, 9)),
    ("JS JD 4H 4C AS 9D 2H", HandCategory.TWO_PAIR, (11, 4, 14)),
    ("JS JD 9H 9C 4S 4D AH", HandCategory.TWO_PAIR, (11, 9, 14)),  # three pairs: kicker is the ace
    ("JS JD 9H 9C 4S 4D 6H", HandCategory.TWO_PAIR, (11, 9, 6)),  # ...and a lower third pair
    ("AS AD KH 9C 7S 4D 2H", HandCategory.ONE_PAIR, (14, 13, 9, 7)),
    ("AS JD 9H 6C 4S 3D 2H", HandCategory.HIGH_CARD, (14, 11, 9, 6, 4)),
]


@pytest.mark.parametrize("codes,category,tiebreak", CASES)
def test_hand_worked_cases(codes: str, category: HandCategory, tiebreak: tuple[int, ...]) -> None:
    result = best_of_seven(seven(codes))
    assert result.category is category and result.tiebreak == tiebreak
    assert engine_key(seven(codes)) == reference_key(seven(codes))


def test_card_order_and_suit_names_do_not_matter() -> None:
    cards = seven("AS KS 9H 9D 4C 4S 2H")
    expected = engine_key(cards)
    generator = random.Random(3)
    for _ in range(30):
        shuffled = list(cards)
        generator.shuffle(shuffled)
        assert engine_key(tuple(shuffled)) == expected
    suits = list(Suit)
    for permutation in itertools.permutations(suits):
        mapping = dict(zip(suits, permutation, strict=True))
        mapped = tuple(Card(card.rank, mapping[card.suit]) for card in cards)
        assert engine_key(mapped) == expected


def test_a_pair_on_the_board_is_played_by_both_and_ties() -> None:
    board = "AS AD 9H 7C 3S"
    low = best_of_seven(seven(f"{board} 2D 4H"))
    same = best_of_seven(seven(f"{board} 2C 4D"))
    assert low.sort_key == same.sort_key  # the same kickers: an exact tie, suits do not matter
    assert best_of_seven(seven(f"{board} 2C 5D")).sort_key > low.sort_key  # a higher kicker wins
    assert best_of_seven(seven(f"{board} KD 4H")).sort_key > low.sort_key  # a king kicker wins


def test_best_of_seven_is_the_maximum_over_every_five_card_subset() -> None:
    generator = random.Random(11)
    for _ in range(150):
        cards = tuple(generator.sample(DECK, 7))
        best = max(evaluate_five(chosen).sort_key for chosen in itertools.combinations(cards, 5))
        assert engine_key(cards) == best


# ---- differential against the independent evaluator ---------------------------------------


def test_random_hands_agree_with_the_independent_evaluator() -> None:
    generator = random.Random(20261117)
    for _ in range(3000):
        cards = tuple(generator.sample(DECK, 7))
        assert engine_key(cards) == reference_key(cards), [c.code for c in cards]


def test_crowded_rank_pools_agree_with_the_independent_evaluator() -> None:
    # Few ranks force pairs, trips, quads, wheels and full houses far more often than a deal.
    generator = random.Random(8)
    pools = [
        [r for r in Rank if r.value in ("A", "2", "3", "4", "5", "6", "K")],
        [r for r in Rank if r.value in ("9", "10", "J", "Q", "K", "A")],
        [r for r in Rank if r.value in ("7", "8", "9")],
        [r for r in Rank if r.value in ("2", "3", "4", "5", "6", "7", "8", "9")],
    ]
    for _ in range(2500):
        pool = [Card(rank, suit) for rank in generator.choice(pools) for suit in Suit]
        if len(pool) < 7:
            continue
        cards = tuple(generator.sample(pool, 7))
        assert engine_key(cards) == reference_key(cards), [c.code for c in cards]


def test_suited_pools_agree_with_the_independent_evaluator() -> None:
    generator = random.Random(9)
    for _ in range(1500):
        main = generator.choice(list(Suit))
        suited = [Card(rank, main) for rank in Rank]
        others = [card for card in DECK if card.suit is not main]
        count = generator.randint(4, 7)
        cards = tuple(generator.sample(suited, count) + generator.sample(others, 7 - count))
        assert engine_key(cards) == reference_key(cards), [c.code for c in cards]


# ---- invalid input -------------------------------------------------------------------------


@pytest.mark.parametrize("size", [0, 5, 6, 8])
def test_the_card_count_must_be_exactly_seven(size: int) -> None:
    with pytest.raises(ValueError, match="exactly 7"):
        best_of_seven(tuple(DECK[:size]))


def test_containers_elements_and_duplicates_are_rejected() -> None:
    cards = seven("AS KS QS JS 10S 2C 3D")
    for bad in (list(cards), None, "AS KS QS JS 10S 2C 3D", iter(cards)):
        with pytest.raises(TypeError, match="must be a tuple"):
            best_of_seven(cast(Any, bad))
    with pytest.raises(TypeError, match="exact Card"):
        best_of_seven(cast(Any, (*cards[:6], "3D")))
    with pytest.raises(TypeError, match="exact Card"):
        best_of_seven(cast(Any, (*cards[:6], CardWithSecret(Rank.THREE, Suit.DIAMONDS))))
    with pytest.raises(ValueError, match="duplicate"):
        best_of_seven((*cards[:6], cards[0]))
