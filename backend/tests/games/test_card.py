from dataclasses import FrozenInstanceError
from operator import lt
from typing import Any, cast

import pytest

from app.games.core import Card, Rank, Suit


@pytest.mark.parametrize("suit", list(Suit))
@pytest.mark.parametrize("rank", list(Rank))
def test_every_legal_card_round_trips(rank: Rank, suit: Suit) -> None:
    card = Card(rank, suit)
    assert Card.from_code(card.code) == card
    assert hash(Card.from_code(card.code)) == hash(card)


def test_standard_faces_are_exactly_the_required_sets() -> None:
    assert {suit.value for suit in Suit} == {"C", "D", "H", "S"}
    assert {rank.value for rank in Rank} == {
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "J",
        "Q",
        "K",
        "A",
    }
    assert Card.from_code("AS") == Card(Rank.ACE, Suit.SPADES)
    assert Card.from_code("10H") == Card(Rank.TEN, Suit.HEARTS)


@pytest.mark.parametrize(
    "code",
    [
        "",
        "A",
        "S",
        "1S",
        "0S",
        "11S",
        "14S",
        "TS",
        "ASJ",
        "AX",
        "JOKER",
        "aS",
        "As",
        "as",
        " AS",
        "AS ",
        "A S",
        "01S",
        "A♠",
        "10",
        "10SS",
        "ＡS",
    ],
)
def test_invalid_card_codes_are_rejected(code: str) -> None:
    with pytest.raises(ValueError, match="Invalid card code"):
        Card.from_code(code)


@pytest.mark.parametrize("code", [None, 14, True, 1.5, b"AS", ["A", "S"]])
def test_card_codes_are_not_coerced(code: object) -> None:
    with pytest.raises(TypeError):
        Card.from_code(cast(str, code))


@pytest.mark.parametrize("rank", [None, "A", 14, 0, True, 2.0, Suit.SPADES])
def test_constructor_rejects_non_rank_values(rank: object) -> None:
    with pytest.raises(TypeError):
        Card(cast(Rank, rank), Suit.SPADES)


@pytest.mark.parametrize("suit", [None, "S", "spades", 0, True, Rank.ACE])
def test_constructor_rejects_non_suit_values(suit: object) -> None:
    with pytest.raises(TypeError):
        Card(Rank.ACE, cast(Suit, suit))


def test_cards_are_immutable_and_do_not_define_game_strength() -> None:
    card = Card(Rank.ACE, Suit.SPADES)
    # Bypass static protection only to verify that runtime checks also enforce it.
    with pytest.raises(FrozenInstanceError):
        cast(Any, card).rank = Rank.KING
    with pytest.raises(TypeError):
        lt(cast(Any, card), cast(Any, Card(Rank.TWO, Suit.CLUBS)))
