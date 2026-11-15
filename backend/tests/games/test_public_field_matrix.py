"""P2-B-R2: exact-type matrix for every public field, including nested values.

Matrix (model.field -> exact type; validation entry):
  Player.id UUID | display_name str | seat int | points int   (Player.__post_init__ and
      re-checked by PublicGameData)
  Turn.player_id UUID                                         (Turn.__post_init__ and re-checked)
  PublicGameData.status GameStatus | state_version int | players tuple[Player, ...]
      | turn Turn | None                                      (PublicGameData.__post_init__)
  GameError.code/message str, request_id UUID | None; GameAction.player_id/request_id UUID,
      state_version int, type str                              (own __post_init__)
bool is rejected for ints; subclasses are rejected for every type, never converted.
"""

from collections.abc import Callable
from dataclasses import asdict, replace
from typing import Any, cast
from uuid import UUID

import pytest

from app.games.core import (
    Card,
    GameAction,
    GameError,
    GameStatus,
    Player,
    PublicGameData,
    Turn,
)

ALICE = UUID(int=1)
BOB = UUID(int=2)
MARKER = "PRIVATE_FIELD_MARKER_4k2"
HAND = (Card.from_code("AS"),)


class DisplayNameWithHand(str):
    """The R2 attack: a str carrying a private attribute."""

    hand: tuple[Card, ...]
    vault: str

    def __new__(cls, value: str) -> "DisplayNameWithHand":
        obj = super().__new__(cls, value)
        obj.hand = HAND
        obj.vault = MARKER
        return obj


class TextWithSecret(str):
    secret: str = MARKER


class UuidWithSecret(UUID):
    secret: str = MARKER


class IntWithSecret(int):
    secret: str = MARKER


class TupleWithSecret(tuple):  # type: ignore[type-arg]
    secret: str = MARKER


def plain() -> PublicGameData:
    return PublicGameData(
        GameStatus.IN_PROGRESS,
        1,
        (Player(ALICE, "Alice", 0, 5), Player(BOB, "Bob", 1, 6)),
        Turn(BOB),
    )


def assert_clean(public: PublicGameData) -> None:
    for text in (repr(asdict(public)), repr(public)):
        for forbidden in (MARKER, "hand", "vault", "secret", "Card("):
            assert forbidden not in text


def test_plain_values_accepted_and_outputs_are_public_only() -> None:
    public = plain()
    first = asdict(public)["players"][0]
    assert first == {"id": ALICE, "display_name": "Alice", "seat": 0, "points": 5}
    assert type(first["display_name"]) is str
    assert type(first["id"]) is UUID
    assert_clean(public)
    assert_clean(replace(public, state_version=2))


def test_display_name_with_hand_is_rejected_at_player_and_public_boundary() -> None:
    name = DisplayNameWithHand("Alice")
    assert name.hand == HAND  # the attack object really carries private data
    with pytest.raises(TypeError, match="display_name must be a string"):
        Player(ALICE, name, 0)
    bypass = Player(ALICE, "Alice", 0)
    object.__setattr__(bypass, "display_name", name)
    with pytest.raises(TypeError, match="display_name must be a string"):
        PublicGameData(GameStatus.WAITING, 0, (bypass,))
    assert_clean(plain())


PLAYER_CASES: list[tuple[str, object]] = [
    ("id", UuidWithSecret(int=1)),
    ("id", "00000000-0000-0000-0000-000000000001"),
    ("display_name", TextWithSecret("Alice")),
    ("display_name", b"Alice"),
    ("seat", IntWithSecret(0)),
    ("seat", True),
    ("points", IntWithSecret(1)),
    ("points", False),
    ("points", 1.0),
    ("points", -1),
]


@pytest.mark.parametrize("field,bad", PLAYER_CASES)
def test_every_player_field_rejects_subclasses_and_wrong_values(field: str, bad: object) -> None:
    kwargs: dict[str, Any] = {"id": ALICE, "display_name": "Alice", "seat": 0, "points": 0}
    kwargs[field] = bad
    with pytest.raises((TypeError, ValueError)):
        Player(**kwargs)
    # Same value injected after construction must still fail at the public boundary.
    bypass = Player(ALICE, "Alice", 0)
    object.__setattr__(bypass, field, bad)
    with pytest.raises((TypeError, ValueError)):
        PublicGameData(GameStatus.WAITING, 0, (bypass,))


def test_turn_player_id_rejects_uuid_subclass_at_both_entries() -> None:
    with pytest.raises(TypeError, match="turn player_id must be a UUID"):
        Turn(UuidWithSecret(int=1))
    bypass = Turn(ALICE)
    object.__setattr__(bypass, "player_id", UuidWithSecret(int=1))
    with pytest.raises(TypeError, match="turn player_id must be a UUID"):
        PublicGameData(GameStatus.WAITING, 0, (Player(ALICE, "Alice", 0),), bypass)


def test_status_and_version_reject_non_exact_values() -> None:
    with pytest.raises(TypeError, match="status must be a GameStatus member"):
        PublicGameData(cast(GameStatus, "waiting"), 0, ())
    with pytest.raises(TypeError, match="state_version must be an integer"):
        PublicGameData(GameStatus.WAITING, IntWithSecret(0), ())
    with pytest.raises(TypeError, match="state_version must be an integer"):
        PublicGameData(GameStatus.WAITING, cast(int, True), ())


def test_enum_cannot_be_subclassed_so_status_has_no_carrier_subclass() -> None:
    with pytest.raises(TypeError, match="cannot extend"):

        class Evil(GameStatus):  # type: ignore[misc]
            pass


def test_players_container_subclass_and_nested_values_are_rejected() -> None:
    p = Player(ALICE, "Alice", 0)
    with pytest.raises(TypeError, match="players must be a tuple"):
        PublicGameData(GameStatus.WAITING, 0, cast(Any, TupleWithSecret((p,))))
    with pytest.raises(TypeError, match="players must be a tuple"):
        PublicGameData(GameStatus.WAITING, 0, cast(Any, [p]))
    with pytest.raises(TypeError, match="players contains an invalid element"):
        PublicGameData(GameStatus.WAITING, 0, cast(Any, (p, (p,))))
    with pytest.raises(TypeError, match="players contains an invalid element"):
        PublicGameData(GameStatus.WAITING, 0, cast(Any, (p, None)))


def test_none_turn_and_wrong_turn_types() -> None:
    assert PublicGameData(GameStatus.WAITING, 0, ()).turn is None
    with pytest.raises(TypeError, match="public turn must be an exact Turn instance"):
        PublicGameData(GameStatus.WAITING, 0, (), cast(Any, {"player_id": ALICE}))


@pytest.mark.parametrize(
    "build",
    [
        lambda: GameError(TextWithSecret("E1"), "msg"),
        lambda: GameError("E1", DisplayNameWithHand("msg")),
        lambda: GameError("E1", "msg", UuidWithSecret(int=1)),
        lambda: GameAction(UuidWithSecret(int=1), BOB, 0, "play"),
        lambda: GameAction(ALICE, UuidWithSecret(int=2), 0, "play"),
        lambda: GameAction(ALICE, BOB, IntWithSecret(0), "play"),
        lambda: GameAction(ALICE, BOB, 0, DisplayNameWithHand("play")),
    ],
)
def test_error_and_action_models_reject_subclass_fields(build: Callable[[], object]) -> None:
    with pytest.raises(TypeError):
        build()


def test_error_and_action_plain_values_still_work() -> None:
    assert asdict(GameError("E1", "msg", BOB))["request_id"] == BOB
    assert GameAction(ALICE, BOB, 0, "play").type == "play"
