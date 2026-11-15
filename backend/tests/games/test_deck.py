from collections.abc import Callable, Iterable
from random import Random
from secrets import SystemRandom
from typing import Any, cast

import pytest

from app.games.core import Card, Deck, InsufficientCardsError, Rank, Suit


def fixed_cards() -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in ("AS", "2C", "10H", "KD", "5S"))


def test_standard_deck_has_exactly_52_distinct_cards() -> None:
    deck = Deck()
    assert not deck.is_test_only
    assert deck.remaining_count == 52
    cards = deck.deal(52)
    assert len(cards) == len(set(cards)) == 52
    assert set(cards) == {Card(rank, suit) for rank in Rank for suit in Suit}
    assert deck.remaining_count == 0


def test_secure_shuffle_preserves_all_cards_after_partial_deal() -> None:
    deck = Deck()
    dealt = deck.deal(13)
    deck.shuffle()
    assert deck.remaining_count == 39
    remaining = deck.deal(39)
    assert set(dealt).isdisjoint(remaining)
    assert set(dealt + remaining) == {Card(rank, suit) for rank in Rank for suit in Suit}


def test_each_single_deal_is_unique_and_updates_remaining_count() -> None:
    deck = Deck()
    seen: set[Card] = set()
    for expected_remaining in range(51, -1, -1):
        hand = deck.deal()
        assert isinstance(hand, tuple)
        assert len(hand) == 1
        assert hand[0] not in seen
        seen.add(hand[0])
        assert deck.remaining_count == expected_remaining


def test_production_create_reset_and_shuffle_always_use_system_random(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    original_shuffle = SystemRandom.shuffle

    def observe(random: SystemRandom, cards: list[Card]) -> None:
        calls.append(len(cards))
        original_shuffle(random, cards)

    monkeypatch.setattr(SystemRandom, "shuffle", observe)
    deck = Deck()
    deck.deal(2)
    deck.shuffle()
    deck.reset()
    assert calls == [52, 50, 52]
    assert deck.remaining_count == 52
    assert not deck.is_test_only
    assert len(set(deck.deal(52))) == 52


def test_reset_after_exhaustion_starts_a_complete_new_cycle() -> None:
    deck = Deck()
    first_cycle = deck.deal(52)
    deck.reset()
    second_cycle = deck.deal(52)
    assert set(first_cycle) == set(second_cycle)


def test_fixed_order_is_injected_copied_and_reproducible() -> None:
    source = list(fixed_cards())
    first = Deck.for_testing(source)
    source.clear()
    second = Deck.for_testing(iter(fixed_cards()))
    assert first.is_test_only and second.is_test_only
    assert first.deal(2) == second.deal(2) == fixed_cards()[:2]
    assert first.remaining_count == 3
    assert first.deal(3) == second.deal(3) == fixed_cards()[2:]
    first.reset()
    assert first.deal(5) == fixed_cards()
    assert first.is_test_only


def test_fixture_reset_does_not_need_randomness(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_randomness(random: SystemRandom, cards: list[Card]) -> None:
        raise AssertionError("fixed-order test deck unexpectedly used randomness")

    monkeypatch.setattr(SystemRandom, "shuffle", reject_randomness)
    deck = Deck.for_testing(fixed_cards())
    deck.deal(1)
    deck.reset()
    assert deck.deal(5) == fixed_cards()


def test_test_only_marker_survives_shuffle_and_reset() -> None:
    deck = Deck.for_testing(fixed_cards())
    deck.shuffle()
    assert deck.is_test_only
    assert set(deck.deal(5)) == set(fixed_cards())
    deck.reset()
    assert deck.is_test_only
    assert deck.deal(5) == fixed_cards()
    with pytest.raises(AttributeError):
        cast(Any, deck).is_test_only = False


@pytest.mark.parametrize("count", [-1, -100, 6, 100])
def test_invalid_or_excessive_deals_leave_order_and_count_unchanged(count: int) -> None:
    deck = Deck.for_testing(fixed_cards())
    error = InsufficientCardsError if count > 5 else ValueError
    with pytest.raises(error):
        deck.deal(count)
    assert deck.remaining_count == 5
    assert deck.deal(5) == fixed_cards()


@pytest.mark.parametrize("count", [None, True, False, 1.0, "1", [], object()])
def test_deal_does_not_coerce_counts(count: object) -> None:
    deck = Deck.for_testing(fixed_cards())
    with pytest.raises(TypeError):
        deck.deal(cast(int, count))
    assert deck.deal(5) == fixed_cards()


def test_empty_deck_and_zero_count_boundaries() -> None:
    deck = Deck.for_testing(())
    assert deck.remaining_count == 0
    assert deck.deal(0) == ()
    with pytest.raises(InsufficientCardsError):
        deck.deal()
    deck.shuffle()
    deck.reset()
    assert deck.remaining_count == 0
    assert deck.is_test_only
    full = Deck()
    assert full.deal(0) == ()
    assert full.remaining_count == 52


def test_insufficient_cards_after_partial_deal_is_atomic() -> None:
    deck = Deck.for_testing(fixed_cards())
    deck.deal(4)
    with pytest.raises(InsufficientCardsError):
        deck.deal(2)
    assert deck.remaining_count == 1
    assert deck.deal() == fixed_cards()[-1:]


def test_duplicate_cards_and_non_cards_are_rejected() -> None:
    cards = fixed_cards()
    with pytest.raises(ValueError, match="Duplicate"):
        Deck.for_testing([cards[0], Card.from_code(cards[0].code)])
    for invalid in ("AS", None, 14, object()):
        with pytest.raises(TypeError):
            Deck.for_testing(cast(list[Card], [cards[0], invalid]))


@pytest.mark.parametrize("invalid", [None, 1, object(), "AS"])
def test_invalid_fixture_iterables_are_rejected(invalid: object) -> None:
    with pytest.raises(TypeError):
        Deck.for_testing(cast(Iterable[Card], invalid))


def test_more_than_52_cards_cannot_form_a_valid_deck() -> None:
    standard = Deck().deal(52)
    with pytest.raises(ValueError, match="Duplicate"):
        Deck.for_testing((*standard, standard[0]))


@pytest.mark.parametrize(
    "options",
    [
        {"seed": 123},
        {"rng": Random(123)},
        {"cards": fixed_cards()},
        {"shuffle": False},
    ],
)
def test_production_constructor_rejects_unsafe_configuration(options: dict[str, object]) -> None:
    with pytest.raises(TypeError):
        cast(Callable[..., Deck], Deck)(**options)


def test_decks_are_independent_and_repr_hides_card_order() -> None:
    first = Deck.for_testing(fixed_cards())
    second = Deck.for_testing(fixed_cards())
    first.deal(2)
    assert second.remaining_count == 5
    assert first.remaining_count == 3
    assert repr(first) == "Deck(remaining_count=3, is_test_only=True)"
    assert all(card.code not in repr(first) for card in fixed_cards())
