"""P3-00: fail-closed secure shuffling (P2-A risk 1) and a static guard that keeps the
fixed-order test factory out of production code (P2-A risk 2, mitigation only).

The static guard is not a Python sandbox: trusted code in the same process can still
reach Deck.for_testing. It catches accidental use in application modules.
"""

import ast
from pathlib import Path
from secrets import SystemRandom

import pytest

from app.games.core import Card, Deck, require_production_deck
from app.games.core.deck import DeckUnavailableError


def break_randomness(monkeypatch: pytest.MonkeyPatch, error: BaseException | None = None) -> None:
    def fail(self: SystemRandom, cards: list[Card]) -> None:
        cards.reverse()  # half-done work must never become the dealt order
        raise error if error is not None else OSError("no entropy")

    monkeypatch.setattr(SystemRandom, "shuffle", fail)


def test_construction_fails_without_secure_randomness(monkeypatch: pytest.MonkeyPatch) -> None:
    break_randomness(monkeypatch)
    with pytest.raises(OSError, match="no entropy"):
        Deck()


def test_failed_reset_leaves_the_deck_unable_to_deal_until_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck = Deck()
    deck.deal(5)
    with monkeypatch.context() as broken:
        break_randomness(broken)
        with pytest.raises(OSError):
            deck.reset()
    assert not deck.is_available
    for count in (0, 1, 47):
        with pytest.raises(DeckUnavailableError):
            deck.deal(count)
    deck.reset()  # randomness is back: full, shuffled recovery
    assert deck.is_available and deck.remaining_count == 52
    assert len(set(deck.deal(52))) == 52


def test_failed_shuffle_does_not_expose_a_partial_order_and_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck = Deck()
    deck.deal(2)
    with monkeypatch.context() as broken:
        break_randomness(broken)
        with pytest.raises(OSError):
            deck.shuffle()
    with pytest.raises(DeckUnavailableError):
        deck.deal(1)
    deck.shuffle()
    assert deck.is_available
    dealt = deck.deal(deck.remaining_count)
    assert len(dealt) == 50 and len(set(dealt)) == 50


def test_base_exceptions_also_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    deck = Deck()
    with monkeypatch.context() as broken:
        break_randomness(broken, KeyboardInterrupt())
        with pytest.raises(KeyboardInterrupt):
            deck.reset()
    assert not deck.is_available
    deck.reset()
    assert deck.is_available


def test_test_only_decks_never_use_system_random_and_stay_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cards = Deck().deal(10)
    fixture = Deck.for_testing(cards)
    break_randomness(monkeypatch)
    fixture.reset()
    assert fixture.is_available and fixture.deal(10) == cards


def test_engine_gate_rejects_an_unavailable_deck(monkeypatch: pytest.MonkeyPatch) -> None:
    deck = Deck()
    with monkeypatch.context() as broken:
        break_randomness(broken)
        with pytest.raises(OSError):
            deck.reset()
    with pytest.raises(DeckUnavailableError):
        require_production_deck(deck)
    deck.reset()
    assert require_production_deck(deck) is deck


def test_application_modules_never_use_the_fixed_order_factory() -> None:
    app_root = Path(__file__).resolve().parents[2] / "app"
    offenders: list[str] = []
    for path in app_root.rglob("*.py"):
        if path.name == "deck.py" and path.parent.name == "core":
            continue  # the definition site
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Attribute):
                names.append(node.attr)
            elif isinstance(node, ast.Name):
                names.append(node.id)
            elif isinstance(node, ast.ImportFrom):
                names.extend(alias.name for alias in node.names)
            if any(name == "for_testing" or name.endswith("_for_testing") for name in names):
                offenders.append(f"{path.relative_to(app_root)}:{getattr(node, 'lineno', 0)}")
    assert offenders == []
