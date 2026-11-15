"""P3-00: allowlisted public extensions and event payloads (exact types, no subclasses).

Not applicable: Texas-specific fields (P3-01 defines them), authorization (extensions are
public data; private data stays in PrivateGameData).
"""

from dataclasses import asdict, dataclass
from typing import Any, cast
from uuid import UUID

import pytest

from app.games.core import (
    Card,
    EventPayload,
    EventVisibility,
    GameEvent,
    GameState,
    GameStatus,
    Player,
    PlayerView,
    PrivateGameData,
    PrivatePlayerData,
    PublicExtension,
    PublicGameData,
    Turn,
    events_for_viewer,
    project_player_view,
    register_event_payload,
    register_public_extension,
)

ALICE, BOB = UUID(int=1), UUID(int=2)
SECRET_HAND = (Card.from_code("AS"), Card.from_code("KS"))
MARKER = "EXTENSION_SECRET_6p"


@register_public_extension
@dataclass(frozen=True, slots=True)
class TablePot(PublicExtension):
    pot: int

    def __post_init__(self) -> None:
        if type(self.pot) is not int:
            raise TypeError("pot must be an integer")
        if self.pot < 0:
            raise ValueError("pot cannot be negative")


@register_event_payload
@dataclass(frozen=True, slots=True)
class BetAmount(EventPayload):
    amount: int

    def __post_init__(self) -> None:
        if type(self.amount) is not int or self.amount < 0:
            raise ValueError("amount must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class UnregisteredPot(PublicExtension):
    pot: int

    def __post_init__(self) -> None:
        pass


@dataclass(frozen=True, slots=True)
class PotWithSecret(TablePot):
    secret: str = MARKER


def game(extension: PublicExtension | None = None) -> GameState:
    players = (Player(ALICE, "Alice", 0), Player(BOB, "Bob", 1))
    return GameState(
        UUID(int=9),
        "stub",
        "1",
        PublicGameData(GameStatus.IN_PROGRESS, 1, players, Turn(ALICE)),
        PrivateGameData(
            (PrivatePlayerData(ALICE, SECRET_HAND), PrivatePlayerData(BOB)),
            (Card.from_code("2C"),),
        ),
        extension,
    )


# ---- registration ----------------------------------------------------------------


def test_registration_rejects_unsafe_or_malformed_classes() -> None:
    @dataclass(frozen=True)
    class NoSlots(PublicExtension):
        pot: int = 0

        def __post_init__(self) -> None:
            pass

    @dataclass(slots=True)
    class NotFrozen(PublicExtension):
        pot: int = 0

        def __post_init__(self) -> None:
            pass

    @dataclass(frozen=True, slots=True)
    class NoValidation(PublicExtension):
        pot: int = 0

    class NotDataclass(PublicExtension):
        __slots__ = ()

    for bad, error in [
        (PublicExtension, TypeError),
        (int, TypeError),
        (NotDataclass, TypeError),
        (NoSlots, ValueError),
        (NotFrozen, ValueError),
        (NoValidation, ValueError),
        (TablePot, ValueError),  # duplicate
        (BetAmount, TypeError),  # a payload class is not a public extension
        ("TablePot", TypeError),
        (TablePot(1), TypeError),
    ]:
        with pytest.raises(error):
            register_public_extension(cast(Any, bad))


def test_payload_registry_is_separate_and_rejects_duplicates() -> None:
    with pytest.raises(ValueError, match="already registered"):
        register_event_payload(BetAmount)
    with pytest.raises(TypeError):
        register_event_payload(cast(Any, TablePot))


# ---- carriers --------------------------------------------------------------------


def test_registered_extension_and_payload_are_accepted_and_serialize_publicly() -> None:
    state = game(TablePot(30))
    assert state.extension == TablePot(30)
    assert asdict(state)["extension"] == {"pot": 30}
    view = PlayerView(ALICE, state.public, PrivatePlayerData(ALICE, SECRET_HAND), TablePot(30))
    assert view.extension == TablePot(30)
    event = GameEvent(1, "bet", EventVisibility.PUBLIC, payload=BetAmount(5))
    assert asdict(event)["payload"] == {"amount": 5}
    assert game().extension is None
    assert GameEvent(2, "x", EventVisibility.PUBLIC).payload is None


@pytest.mark.parametrize(
    "bad",
    [
        {"pot": 1},
        "pot",
        1,
        UnregisteredPot(1),
        PotWithSecret(1),
        BetAmount(1),
    ],
)
def test_state_and_view_reject_anything_but_an_exact_registered_extension(bad: object) -> None:
    with pytest.raises(TypeError, match="exact registered public extension"):
        game(cast(PublicExtension, bad))
    state = game()
    with pytest.raises(TypeError, match="exact registered public extension"):
        PlayerView(ALICE, state.public, PrivatePlayerData(ALICE), cast(PublicExtension, bad))


@pytest.mark.parametrize("bad", [{"amount": 1}, "bet", UnregisteredPot(1), TablePot(1), 5])
def test_event_rejects_anything_but_an_exact_registered_payload(bad: object) -> None:
    with pytest.raises(TypeError, match="exact registered event payload"):
        GameEvent(1, "bet", EventVisibility.PUBLIC, payload=cast(EventPayload, bad))


def test_subclass_carrying_a_private_attribute_never_reaches_serialization() -> None:
    carrier = PotWithSecret(1)
    assert MARKER in repr(asdict(carrier))  # the attack object really carries the secret
    with pytest.raises(TypeError):
        game(carrier)


def test_invalid_field_values_are_rejected_by_the_extension_itself() -> None:
    for bad in (-1, True, 1.5, "1"):
        with pytest.raises((TypeError, ValueError)):
            TablePot(cast(int, bad))


# ---- projection and events -------------------------------------------------------


def test_projection_carries_a_rebuilt_extension_and_never_the_private_hand() -> None:
    state = game(TablePot(30))
    view = project_player_view(state, BOB)
    assert isinstance(view, PlayerView)
    assert view.extension == TablePot(30) and view.extension is not state.extension
    text = repr(view) + repr(asdict(view.public)) + repr(asdict(view))
    for card in (*SECRET_HAND, *state.private.remaining_cards):
        assert repr(card) not in text and card.code not in text.replace("\n", " ").split()


def test_projection_revalidates_an_extension_altered_after_construction() -> None:
    state = game(TablePot(30))
    assert state.extension is not None
    object.__setattr__(state.extension, "pot", -5)
    with pytest.raises(ValueError, match="pot cannot be negative"):
        project_player_view(state, ALICE)


def test_event_payload_visibility_follows_the_event() -> None:
    events = (
        GameEvent(1, "dealt", EventVisibility.PRIVATE, ALICE, BetAmount(1)),
        GameEvent(2, "bet", EventVisibility.PUBLIC, payload=BetAmount(5)),
    )
    assert [e.seq for e in events_for_viewer(events, ALICE)] == [1, 2]
    assert [e.seq for e in events_for_viewer(events, BOB)] == [2]
