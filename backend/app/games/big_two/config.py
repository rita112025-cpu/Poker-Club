from app.games.core.card import Card, Rank, Suit
from app.games.core.engine_types import GameConfig

CONFIG = GameConfig("big_two", "taiwan-four-v1")
PLAYER_COUNT = 4
HAND_SIZE = 13
OPENING_CARD = Card(Rank.THREE, Suit.CLUBS)
RANKS = tuple(Rank(value) for value in "3 4 5 6 7 8 9 10 J Q K A 2".split())
SUITS = (Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES)
STRAIGHTS = tuple(tuple(range(start, start + 5)) for start in range(8))


def card_key(card: Card) -> tuple[int, int]:
    return RANKS.index(card.rank), SUITS.index(card.suit)
