"""P2-E: Texas five-card hand evaluation.

Independent oracle: the well-known counts of the 2,598,960 five-card hands per category
and the 7,462 distinct hand strengths, derived here by rank-multiset enumeration
(suit assignments counted combinatorially), not by re-running the evaluator on every hand.
Not applicable: best-of-seven, betting, pots, other games (later phases).
"""

import ast
import itertools
import random
from dataclasses import FrozenInstanceError, dataclass
from math import comb
from pathlib import Path
from typing import Any, cast

import pytest

from app.games.core import Card, Rank, Suit
from app.games.texas_holdem import HandCategory, HandRank, compare, evaluate_five

C = HandCategory
RANK_ORDER = list(Rank)
SUIT_ORDER = list(Suit)


def hand(codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes.split())


def rank(codes: str) -> HandRank:
    return evaluate_five(hand(codes))


class IntWithSecret(int):
    secret = "HAND_SECRET"


class TupleWithSecret(tuple):  # type: ignore[type-arg]
    secret = "HAND_SECRET"


@dataclass(frozen=True, slots=True)
class CardWithSecret(Card):
    secret: str = "HAND_SECRET"


# ---- categories and tiebreak keys -----------------------------------------

CATEGORY_CASES = [
    ("AS KS QS JS 10S", C.STRAIGHT_FLUSH, (14,)),  # royal flush = ace-high straight flush
    ("9H 8H 7H 6H 5H", C.STRAIGHT_FLUSH, (9,)),
    ("AD 2D 3D 4D 5D", C.STRAIGHT_FLUSH, (5,)),  # steel wheel
    ("9S 9H 9D 9C KS", C.FOUR_OF_A_KIND, (9, 13)),
    ("2S 2H 2D 2C AS", C.FOUR_OF_A_KIND, (2, 14)),
    ("KS KH KD 4C 4S", C.FULL_HOUSE, (13, 4)),
    ("4S 4H 4D KC KS", C.FULL_HOUSE, (4, 13)),
    ("AH JH 9H 6H 3H", C.FLUSH, (14, 11, 9, 6, 3)),
    ("10S 9D 8H 7C 6S", C.STRAIGHT, (10,)),
    ("AS KD QH JC 10S", C.STRAIGHT, (14,)),
    ("AS 2D 3H 4C 5S", C.STRAIGHT, (5,)),  # wheel
    ("7S 7H 7D KC 2S", C.THREE_OF_A_KIND, (7, 13, 2)),
    ("JS JH 4D 4C AS", C.TWO_PAIR, (11, 4, 14)),
    ("5S 5H AD KC 2S", C.ONE_PAIR, (5, 14, 13, 2)),
    ("AS JD 9H 6C 3S", C.HIGH_CARD, (14, 11, 9, 6, 3)),
]


@pytest.mark.parametrize("codes,category,tiebreak", CATEGORY_CASES)
def test_each_category_and_tiebreak_key(
    codes: str, category: HandCategory, tiebreak: tuple[int, ...]
) -> None:
    assert rank(codes) == HandRank(category, tiebreak)


def test_no_wraparound_straights_are_not_straights() -> None:
    assert rank("QS KH AD 2C 3S").category is C.HIGH_CARD
    assert rank("JS QH KD AC 2S").category is C.HIGH_CARD
    assert rank("KS AH 2D 3C 4S").category is C.HIGH_CARD
    assert rank("QS KH AD 2S 3S").category is C.HIGH_CARD  # not a flush either
    assert rank("QS KS AS 2S 3S").category is C.FLUSH


# ---- ordering --------------------------------------------------------------

ASCENDING = [
    "7S 5H 4D 3C 2S",  # 7-high
    "AS KD QH JC 9S",  # ace-high
    "2S 2H 5D 4C 3S",  # pair of 2s, kickers 5 4 3
    "2S 2H 6D 4C 3S",  # kicker 6 beats 5
    "AS AH 4D 3C 2S",  # pair of aces
    "3S 3H 2D 2C 4S",  # two pair 3s/2s
    "3S 3H 2D 2C AS",  # better kicker
    "4S 4H 2D 2C 3S",  # higher top pair
    "2S 2H 2D 5C 3S",  # trips
    "3S 3H 3D 2C 4S",
    "AS 2H 3D 4C 5S",  # wheel
    "2S 3H 4D 5C 6S",  # 6-high straight beats wheel
    "10S 9H 8D 7C 6S",
    "AS KH QD JC 10S",
    "7H 5H 4H 3H 2H",  # flush
    "8H 5H 4H 3H 2H",
    "AH 5H 4H 3H 7H",  # ace-high flush
    "2S 2H 2D 3C 3S",  # full house
    "2S 2H 2D 4C 4S",
    "3S 3H 3D 2C 2S",
    "2S 2H 2D 2C 3S",  # quads
    "2S 2H 2D 2C AS",
    "3S 3H 3D 3C 2S",
    "AD 2D 3D 4D 5D",  # steel wheel
    "2D 3D 4D 5D 6D",
    "AS KS QS JS 10S",  # royal flush
]


def test_strict_total_order_over_representative_hands() -> None:
    ranks = [rank(codes) for codes in ASCENDING]
    for low, high in itertools.combinations(range(len(ranks)), 2):
        assert compare(ranks[low], ranks[high]) == -1, (ASCENDING[low], ASCENDING[high])
        assert compare(ranks[high], ranks[low]) == 1
    for item in ranks:
        assert compare(item, item) == 0


def test_ties_ignore_suits_for_every_category() -> None:
    pairs = [
        ("9S 9H KD 4C 2S", "9D 9C KH 4S 2H"),
        ("AS KD QH JC 9S", "AH KS QD JS 9C"),
        ("AS 2D 3H 4C 5S", "AD 2H 3C 4S 5H"),
        ("AH JH 9H 6H 3H", "AS JS 9S 6S 3S"),
        ("AS KS QS JS 10S", "AH KH QH JH 10H"),
        ("2S 2H 2D 3C 3S", "2C 2H 2D 3S 3H"),
    ]
    for first, second in pairs:
        assert compare(rank(first), rank(second)) == 0


def test_tied_hands_that_differ_only_in_suit_assignment_are_equal_values() -> None:
    assert rank("AH JH 9H 6H 3H") == rank("AS JS 9S 6S 3S")
    assert hash(rank("AH JH 9H 6H 3H")) == hash(rank("AS JS 9S 6S 3S"))


@pytest.mark.parametrize("codes", [case[0] for case in CATEGORY_CASES])
def test_card_order_and_suit_permutation_do_not_change_the_result(codes: str) -> None:
    cards = hand(codes)
    expected = evaluate_five(cards)
    for permutation in itertools.permutations(cards):
        assert evaluate_five(permutation) == expected
    flush = len({card.suit for card in cards}) == 1
    for suits in itertools.permutations(SUIT_ORDER):
        mapping = dict(zip(SUIT_ORDER, suits, strict=True))
        mapped = tuple(Card(card.rank, mapping[card.suit]) for card in cards)
        assert evaluate_five(mapped) == expected
        assert (len({card.suit for card in mapped}) == 1) == flush


# ---- invalid input and adversarial values ----------------------------------


@pytest.mark.parametrize("size", [0, 1, 4, 6, 7])
def test_wrong_card_count_is_rejected(size: int) -> None:
    cards = tuple(Card(RANK_ORDER[index], Suit.CLUBS) for index in range(size))
    with pytest.raises(ValueError, match="exactly 5"):
        evaluate_five(cards)


@pytest.mark.parametrize(
    "bad",
    [
        None,
        list(hand("AS KS QS JS 10S")),
        "AS KS QS JS 10S",
        TupleWithSecret(hand("AS KS QS JS 10S")),
        iter(hand("AS KS QS JS 10S")),
    ],
)
def test_non_tuple_containers_are_rejected(bad: object) -> None:
    with pytest.raises(TypeError, match="cards must be a tuple"):
        evaluate_five(cast(Any, bad))


def test_non_card_and_subclass_elements_are_rejected() -> None:
    base = hand("AS KS QS JS 10S")
    for bad in ("AS", None, 14, ("A", "S"), CardWithSecret(Rank.TEN, Suit.SPADES)):
        with pytest.raises(TypeError, match="exact Card"):
            evaluate_five(cast(Any, (*base[:4], bad)))


def test_duplicate_cards_are_rejected_even_with_valid_count() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_five(hand("AS AS KS QS JS"))


def test_hand_rank_validates_its_own_fields() -> None:
    HandRank(C.STRAIGHT, (5,))
    bad_values: list[Any] = [
        (C.STRAIGHT, (5, 4)),
        (C.STRAIGHT, [5]),
        (C.STRAIGHT, TupleWithSecret((5,))),
        (C.STRAIGHT, (IntWithSecret(5),)),
        (C.STRAIGHT, (True,)),
        (C.STRAIGHT, (1,)),
        (C.STRAIGHT, (15,)),
        ("straight", (5,)),
        (C.FULL_HOUSE, (3,)),
    ]
    for category, tiebreak in bad_values:
        with pytest.raises((TypeError, ValueError)):
            HandRank(category, tiebreak)


def test_results_are_immutable_and_compare_rejects_non_ranks() -> None:
    result = rank("AS KS QS JS 10S")
    with pytest.raises(FrozenInstanceError):
        cast(Any, result).category = C.HIGH_CARD
    with pytest.raises((AttributeError, TypeError)):  # slots + frozen: no stray state
        cast(Any, result).extra = 1
    for bad in (None, (8, (14,)), "straight_flush"):
        with pytest.raises(TypeError, match="exact HandRank"):
            compare(result, cast(Any, bad))
        with pytest.raises(TypeError, match="exact HandRank"):
            compare(cast(Any, bad), result)


def test_strength_is_explicit_and_independent_of_enum_declaration_order() -> None:
    # Declaration order of Rank/Suit/HandCategory carries no meaning; the expected order
    # is spelled out here and checked against the evaluator's own results.
    expected = [
        C.HIGH_CARD,
        C.ONE_PAIR,
        C.TWO_PAIR,
        C.THREE_OF_A_KIND,
        C.STRAIGHT,
        C.FLUSH,
        C.FULL_HOUSE,
        C.FOUR_OF_A_KIND,
        C.STRAIGHT_FLUSH,
    ]
    best = {case[1]: rank(case[0]) for case in CATEGORY_CASES}
    ordered = sorted(best.values(), key=lambda item: item.sort_key)
    assert [item.category for item in ordered] == expected
    assert compare(rank("AS AH 3D 4C 5S"), rank("KS KH QD JC 9S")) == 1
    assert compare(rank("2S 3H 4D 5C 7S"), rank("AS KH QD JC 9S")) == -1


# ---- oracle ------------------------------------------------------------------

EXPECTED_COUNTS = {
    C.STRAIGHT_FLUSH: 40,
    C.FOUR_OF_A_KIND: 624,
    C.FULL_HOUSE: 3744,
    C.FLUSH: 5108,
    C.STRAIGHT: 10200,
    C.THREE_OF_A_KIND: 54912,
    C.TWO_PAIR: 123552,
    C.ONE_PAIR: 1098240,
    C.HIGH_CARD: 1302540,
}


def _representative(ranks: tuple[int, ...], flush: bool) -> tuple[Card, ...]:
    used: dict[int, int] = {}
    cards = []
    for index, value in enumerate(ranks):
        seen = used.get(value, 0)
        used[value] = seen + 1
        if flush:
            suit = SUIT_ORDER[0]
        elif seen:
            suit = SUIT_ORDER[seen]
        else:
            suit = SUIT_ORDER[1 if index == 4 else 0]  # 4 same-suit + 1 different if all distinct
        cards.append(Card(RANK_ORDER[value], suit))
    return tuple(cards)


def _oracle_counts() -> tuple[dict[HandCategory, int], set[tuple[int, tuple[int, ...]]], int]:
    counts: dict[HandCategory, int] = dict.fromkeys(HandCategory, 0)
    keys: set[tuple[int, tuple[int, ...]]] = set()
    total = 0
    for ranks in itertools.combinations_with_replacement(range(13), 5):
        multiplicities = [ranks.count(value) for value in set(ranks)]
        if max(multiplicities) > 4:
            continue
        weight = 1
        for multiplicity in multiplicities:
            weight *= comb(4, multiplicity)
        if len(multiplicities) == 5:  # distinct ranks: 4 flush assignments, the rest are not
            flush_weight, plain_weight = 4, weight - 4
            variants = [(True, flush_weight), (False, plain_weight)]
        else:
            variants = [(False, weight)]
        for flush, amount in variants:
            result = evaluate_five(_representative(ranks, flush))
            counts[result.category] += amount
            keys.add(result.sort_key)
            total += amount
    return counts, keys, total


def test_category_counts_and_distinct_strengths_match_the_known_five_card_oracle() -> None:
    counts, keys, total = _oracle_counts()
    assert total == comb(52, 5) == 2_598_960
    assert counts == EXPECTED_COUNTS
    assert len(keys) == 7462


def test_random_concrete_hands_match_their_rank_multiset_representative() -> None:
    generator = random.Random(20261115)
    deck = [Card(rank_, suit) for rank_ in Rank for suit in Suit]
    for _ in range(20_000):
        cards = tuple(generator.sample(deck, 5))
        flush = len({card.suit for card in cards}) == 1
        ranks = tuple(sorted(RANK_ORDER.index(card.rank) for card in cards))
        distinct = len(set(ranks)) == 5
        expected = evaluate_five(_representative(ranks, flush if distinct else False))
        assert evaluate_five(cards) == expected


# ---- boundaries --------------------------------------------------------------


def test_module_depends_statically_only_on_card() -> None:
    path = Path(__file__).resolve().parents[2] / "app" / "games" / "texas_holdem" / "hands.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    internal = {name for name in modules if name.startswith("app")}
    assert internal == {"app.games.core.card"}
    forbidden = {"fastapi", "starlette", "sqlalchemy", "pydantic", "alembic", "random", "secrets"}
    assert not {name.split(".")[0] for name in modules} & forbidden


# ---- P3-00: HandRank semantic validation ----------------------------------------


def test_hand_rank_accepts_exactly_the_reachable_tiebreaks_of_every_category() -> None:
    from app.games.texas_holdem.hands import _TIEBREAK_LENGTH, _is_possible

    accepted = {
        category: sum(
            1
            for tiebreak in itertools.product(range(2, 15), repeat=length)
            if _is_possible(category, tiebreak)
        )
        for category, length in _TIEBREAK_LENGTH.items()
    }
    # Distinct strengths per category (10/156/156/1277/10/858/858/2860/1277 = 7462).
    assert accepted == {
        C.STRAIGHT_FLUSH: 10,
        C.FOUR_OF_A_KIND: 156,
        C.FULL_HOUSE: 156,
        C.FLUSH: 1277,
        C.STRAIGHT: 10,
        C.THREE_OF_A_KIND: 858,
        C.TWO_PAIR: 858,
        C.ONE_PAIR: 2860,
        C.HIGH_CARD: 1277,
    }
    assert sum(accepted.values()) == 7462


def test_constructor_agrees_with_the_semantic_predicate_on_random_tuples() -> None:
    from app.games.texas_holdem.hands import _TIEBREAK_LENGTH, _is_possible

    generator = random.Random(20261116)
    for _ in range(6000):
        category = generator.choice(list(HandCategory))
        tiebreak = tuple(generator.randint(2, 14) for _ in range(_TIEBREAK_LENGTH[category]))
        if _is_possible(category, tiebreak):
            assert HandRank(category, tiebreak).tiebreak == tiebreak
        else:
            with pytest.raises(ValueError, match="impossible"):
                HandRank(category, tiebreak)


def test_impossible_tiebreaks_found_by_the_reviewer_are_rejected() -> None:
    impossible = [
        (C.STRAIGHT, (2,)),
        (C.FULL_HOUSE, (5, 5)),
        (C.FLUSH, (2, 3, 4, 5, 6)),
        (C.STRAIGHT_FLUSH, (3,)),
        (C.FLUSH, (9, 9, 9, 9, 9)),
        (C.FLUSH, (14, 5, 4, 3, 2)),  # that hand is a steel wheel, not a flush
        (C.FOUR_OF_A_KIND, (7, 7)),
        (C.TWO_PAIR, (4, 9, 2)),
        (C.TWO_PAIR, (9, 4, 9)),
        (C.ONE_PAIR, (5, 5, 4, 3)),
        (C.THREE_OF_A_KIND, (7, 3, 9)),
    ]
    for category, tiebreak in impossible:
        with pytest.raises(ValueError, match="impossible"):
            HandRank(category, tiebreak)
