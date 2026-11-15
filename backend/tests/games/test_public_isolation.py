from collections.abc import Callable
from dataclasses import FrozenInstanceError, asdict, dataclass, field, replace
from typing import Any, cast
from uuid import UUID

import pytest

from app.games.core import (
    Card,
    GameState,
    GameStatus,
    Player,
    PlayerView,
    PrivateGameData,
    PrivatePlayerData,
    PublicGameData,
    Turn,
)

ALICE = UUID(int=1)
BOB = UUID(int=2)
SESSION = UUID(int=3)
PRIVATE_MARKER = "PRIVATE_HAND_MARKER_9x7"


@dataclass(frozen=True, slots=True)
class PlayerWithHand(Player):
    hand: tuple[Card, ...] = ()


@dataclass(frozen=True, slots=True)
class PlayerWithHiddenHand(Player):
    hand: tuple[Card, ...] = field(default=(), repr=False)


@dataclass(frozen=True, slots=True)
class PlayerWithSecret(Player):
    secret: str = PRIVATE_MARKER


@dataclass(frozen=True, slots=True)
class TurnWithHand(Turn):
    hand: tuple[Card, ...] = ()


@dataclass(frozen=True, slots=True)
class ExtendedPublicData(PublicGameData):
    secret: str = PRIVATE_MARKER


@dataclass(frozen=True, slots=True)
class UncheckedPublicData(PublicGameData):
    secret: str = PRIVATE_MARKER

    def __post_init__(self) -> None:
        # Simulate an internal extension that omits the base validation.
        pass


def public_data() -> PublicGameData:
    return PublicGameData(
        GameStatus.IN_PROGRESS,
        7,
        (Player(ALICE, "Alice", 0, 100), Player(BOB, "Bob", 1, 200)),
        Turn(ALICE),
    )


def assert_safe_output(public: PublicGameData) -> None:
    output = asdict(public)
    assert output == {
        "status": GameStatus.IN_PROGRESS,
        "state_version": 7,
        "players": (
            {"id": ALICE, "display_name": "Alice", "seat": 0, "points": 100},
            {"id": BOB, "display_name": "Bob", "seat": 1, "points": 200},
        ),
        "turn": {"player_id": ALICE},
    }
    assert repr(public) == (
        "PublicGameData(status=<GameStatus.IN_PROGRESS: 'in_progress'>, state_version=7, "
        f"players=(Player(id={ALICE!r}, display_name='Alice', seat=0, points=100), "
        f"Player(id={BOB!r}, display_name='Bob', seat=1, points=200)), "
        f"turn=Turn(player_id={ALICE!r}))"
    )
    for text in (repr(output), repr(public)):
        for forbidden in ("hand", "secret", PRIVATE_MARKER, "Card(", "Rank.ACE", "Suit.SPADES"):
            assert forbidden not in text


def test_plain_players_remain_compatible_and_outputs_are_public_only() -> None:
    public = public_data()
    assert_safe_output(public)
    copied = PublicGameData(public.status, public.state_version, public.players, public.turn)
    assert copied.players is public.players
    assert copied.players[0] is public.players[0]
    assert copied.turn is public.turn
    assert_safe_output(copied)


@pytest.mark.parametrize("position", [0, 1])
@pytest.mark.parametrize("model", [PlayerWithHand, PlayerWithHiddenHand, PlayerWithSecret])
def test_player_extensions_are_rejected_without_changing_safe_outputs(
    model: type[Player], position: int
) -> None:
    public = public_data()
    players = list(public.players)
    original = players[position]
    if model in (PlayerWithHand, PlayerWithHiddenHand):
        extended = cast(Callable[..., Player], model)(
            original.id,
            original.display_name,
            original.seat,
            original.points,
            (Card.from_code("AS"),),
        )
        # Demonstrate that repr=False does not remove a dataclass field from asdict.
        assert asdict(extended)["hand"] == (
            {"rank": Card.from_code("AS").rank, "suit": Card.from_code("AS").suit},
        )
    else:
        extended = model(original.id, original.display_name, original.seat, original.points)
        assert asdict(extended)["secret"] == PRIVATE_MARKER
    players[position] = extended
    with pytest.raises(TypeError, match="public player must be an exact Player instance") as error:
        replace(public, players=tuple(players))
    assert "subclasses are not allowed" in str(error.value)
    assert PRIVATE_MARKER not in str(error.value)
    assert "Card(" not in str(error.value)
    assert_safe_output(public)


def test_reviewers_player_with_hand_example_cannot_construct_public_data() -> None:
    player = PlayerWithHand(ALICE, "Alice", 0, 0, (Card.from_code("AS"),))
    assert "hand=" in repr(player)
    assert "hand" in asdict(player)
    with pytest.raises(TypeError, match="public player must be an exact Player instance"):
        PublicGameData(GameStatus.IN_PROGRESS, 0, (player,))
    assert_safe_output(public_data())


@pytest.mark.parametrize("invalid", [None, "Alice", {}, ("hand",), object()])
def test_non_player_input_is_rejected_without_implicit_conversion(invalid: object) -> None:
    public = public_data()
    with pytest.raises(TypeError, match="players contains an invalid element"):
        replace(public, players=cast(tuple[Player, ...], (invalid,)))
    assert_safe_output(public)


def test_dictionary_with_public_and_private_keys_is_not_converted_to_player() -> None:
    external = {
        "id": ALICE,
        "display_name": "Alice",
        "seat": 0,
        "points": 100,
        "hand": (Card.from_code("AS"),),
        "secret": PRIVATE_MARKER,
    }
    with pytest.raises(TypeError, match="players contains an invalid element"):
        PublicGameData(GameStatus.WAITING, 0, cast(tuple[Player, ...], (external,)))
    assert_safe_output(public_data())


def test_turn_extension_cannot_reintroduce_private_fields() -> None:
    public = public_data()
    turn = TurnWithHand(ALICE, (Card.from_code("AS"),))
    assert "hand" in asdict(turn)
    with pytest.raises(TypeError, match="public turn must be an exact Turn instance"):
        replace(public, turn=turn)
    assert_safe_output(public)


def test_public_container_extension_is_rejected_by_inherited_validation() -> None:
    public = public_data()
    with pytest.raises(TypeError, match="public must be an exact PublicGameData instance"):
        ExtendedPublicData(public.status, public.state_version, public.players, public.turn)
    assert_safe_output(public)


@pytest.mark.parametrize("consumer", ["state", "view"])
def test_public_consumers_reject_an_extension_that_skips_its_base_validation(consumer: str) -> None:
    public = public_data()
    extended = UncheckedPublicData(
        public.status,
        public.state_version,
        public.players,
        public.turn,
    )
    assert asdict(extended)["secret"] == PRIVATE_MARKER
    with pytest.raises(TypeError, match="public must be an exact PublicGameData instance"):
        if consumer == "state":
            GameState(SESSION, "big_two", "1", extended, PrivateGameData())
        else:
            PlayerView(ALICE, extended, PrivatePlayerData(ALICE))
    assert_safe_output(public)


def test_empty_plain_public_data_and_dataclass_replacement_still_work() -> None:
    empty = PublicGameData(GameStatus.WAITING, 0, ())
    assert asdict(empty) == {
        "status": GameStatus.WAITING,
        "state_version": 0,
        "players": (),
        "turn": None,
    }
    changed = replace(public_data(), state_version=8)
    assert changed.state_version == 8
    assert type(changed) is PublicGameData
    with pytest.raises(FrozenInstanceError):
        cast(Any, changed).state_version = 9
