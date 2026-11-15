import importlib
import itertools
import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import FrozenInstanceError, asdict, fields, replace
from typing import Any, cast
from uuid import UUID

import pytest

from app.games.core import (
    Card,
    Deck,
    GameAction,
    GameError,
    GameState,
    GameStatus,
    Player,
    PlayerId,
    PlayerView,
    PrivateGameData,
    PrivatePlayerData,
    PublicGameData,
    Turn,
)

ALICE = UUID("11111111-1111-4111-8111-111111111111")
BOB = UUID("22222222-2222-4222-8222-222222222222")
OTHER = UUID("33333333-3333-4333-8333-333333333333")
REQUEST = UUID("44444444-4444-4444-8444-444444444444")
SESSION = UUID("55555555-5555-4555-8555-555555555555")


def roster() -> tuple[Player, ...]:
    return (Player(ALICE, "玩家甲", 0, 100), Player(BOB, "玩家乙", 1, 100))


def public_data() -> PublicGameData:
    return PublicGameData(GameStatus.IN_PROGRESS, 12, roster(), Turn(ALICE))


def test_legal_models_are_data_only_and_preserve_values() -> None:
    alice: PlayerId = ALICE
    public = public_data()
    own = PrivatePlayerData(alice, (Card.from_code("AS"),))
    hidden = PrivateGameData((own,), (Card.from_code("2C"),))
    state = GameState(SESSION, "texas_holdem", "1", public, hidden)
    view = PlayerView(alice, public, own)
    action = GameAction(alice, REQUEST, 12, "call")
    error = GameError("stale_state", "牌局版本已更新", REQUEST)
    assert state.public is public
    assert state.private is hidden
    assert view.private is own
    assert action.player_id == alice
    assert action.request_id == error.request_id == REQUEST
    assert action.state_version == state.public.state_version == 12
    assert action.type == "call"
    assert error.code == "stale_state"


@pytest.mark.parametrize("status", list(GameStatus))
def test_all_lifecycle_statuses_can_be_explicitly_constructed(status: GameStatus) -> None:
    assert GameStatus(status.value) is status
    assert PublicGameData(status, 0, ()).status is status


@pytest.mark.parametrize("invalid", ["waiting", "unknown", None, 0, True])
def test_raw_or_invalid_status_is_rejected(invalid: object) -> None:
    with pytest.raises(TypeError):
        PublicGameData(cast(GameStatus, invalid), 0, ())


def test_unknown_status_value_is_rejected_by_enum() -> None:
    with pytest.raises(ValueError):
        GameStatus("unknown")


@pytest.mark.parametrize(
    "factory",
    [
        lambda value: Player(value, "玩家", 0),
        lambda value: Turn(value),
        lambda value: GameAction(value, REQUEST, 0, "call"),
        lambda value: GameAction(ALICE, value, 0, "call"),
        lambda value: GameError("stale_state", "錯誤", value),
        lambda value: PrivatePlayerData(value),
        lambda value: GameState(value, "big_two", "1", public_data(), PrivateGameData()),
        lambda value: PlayerView(value, public_data(), PrivatePlayerData(ALICE)),
    ],
)
@pytest.mark.parametrize("invalid", ["not-a-uuid", 1, True])
def test_identity_fields_require_uuid_instances(
    factory: Callable[[Any], object], invalid: object
) -> None:
    with pytest.raises(TypeError):
        factory(invalid)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: Player(cast(PlayerId, None), "玩家", 0),
        lambda: Turn(cast(PlayerId, None)),
        lambda: GameAction(cast(PlayerId, None), REQUEST, 0, "call"),
        lambda: GameAction(ALICE, cast(UUID, None), 0, "call"),
        lambda: PrivatePlayerData(cast(PlayerId, None)),
        lambda: GameState(cast(UUID, None), "big_two", "1", public_data(), PrivateGameData()),
        lambda: PlayerView(cast(PlayerId, None), public_data(), PrivatePlayerData(ALICE)),
    ],
)
def test_required_uuid_fields_cannot_be_none(factory: Callable[[], object]) -> None:
    with pytest.raises(TypeError):
        factory()


@pytest.mark.parametrize(
    "factory",
    [
        lambda value: Player(ALICE, "玩家", value),
        lambda value: Player(ALICE, "玩家", 0, value),
        lambda value: PublicGameData(GameStatus.WAITING, value, ()),
        lambda value: GameAction(ALICE, REQUEST, value, "call"),
    ],
)
@pytest.mark.parametrize("invalid", [-1, True, 1.0, "1", None])
def test_nonnegative_integer_fields_are_strict(
    factory: Callable[[Any], object], invalid: object
) -> None:
    with pytest.raises((TypeError, ValueError)):
        factory(invalid)


@pytest.mark.parametrize(
    "factory",
    [
        lambda value: Player(ALICE, value, 0),
        lambda value: GameAction(ALICE, REQUEST, 0, value),
        lambda value: GameError(value, "錯誤"),
        lambda value: GameError("stale_state", value),
        lambda value: GameState(SESSION, value, "1", public_data(), PrivateGameData()),
        lambda value: GameState(SESSION, "big_two", value, public_data(), PrivateGameData()),
    ],
)
@pytest.mark.parametrize("invalid", ["", " \t\n", None, 1])
def test_required_text_fields_reject_blank_or_non_text(
    factory: Callable[[Any], object], invalid: object
) -> None:
    with pytest.raises((TypeError, ValueError)):
        factory(invalid)


@pytest.mark.parametrize(
    "model",
    [Player, Turn, GameAction, GameError, GameState, PublicGameData, PrivatePlayerData, PlayerView],
)
def test_required_fields_cannot_be_omitted(model: Callable[..., object]) -> None:
    with pytest.raises(TypeError):
        model()


def test_empty_private_data_and_optional_request_id_are_valid() -> None:
    assert PrivateGameData().players == ()
    assert PrivatePlayerData(ALICE).hand == ()
    assert GameError("invalid_action", "操作無效").request_id is None
    assert Player(ALICE, "玩家", 0).points == 0


def test_public_roster_and_turn_referential_checks() -> None:
    first, second = roster()
    with pytest.raises(ValueError, match="duplicate identities"):
        PublicGameData(GameStatus.WAITING, 0, (first, replace(second, id=ALICE)))
    with pytest.raises(ValueError, match="share a seat"):
        PublicGameData(GameStatus.WAITING, 0, (first, replace(second, seat=0)))
    with pytest.raises(ValueError, match="turn player"):
        PublicGameData(GameStatus.IN_PROGRESS, 0, roster(), Turn(OTHER))
    with pytest.raises(TypeError, match="turn"):
        PublicGameData(GameStatus.IN_PROGRESS, 0, roster(), cast(Turn, ALICE))


@pytest.mark.parametrize(
    "factory",
    [
        lambda value: PublicGameData(GameStatus.WAITING, 0, value),
        lambda value: PrivateGameData(value),
        lambda value: PrivatePlayerData(ALICE, value),
        lambda value: PrivateGameData(remaining_cards=value),
    ],
)
@pytest.mark.parametrize("invalid", [[], {}, None, ("invalid",)])
def test_collections_require_immutable_tuples_of_correct_elements(
    factory: Callable[[Any], object], invalid: object
) -> None:
    with pytest.raises(TypeError):
        factory(invalid)


def test_private_cards_and_players_cannot_be_duplicated() -> None:
    ace = Card.from_code("AS")
    with pytest.raises(ValueError, match="duplicate cards"):
        PrivatePlayerData(ALICE, (ace, Card.from_code("AS")))
    with pytest.raises(ValueError, match="duplicate cards"):
        PrivateGameData(remaining_cards=(ace, ace))
    with pytest.raises(ValueError, match="duplicate identities"):
        PrivateGameData((PrivatePlayerData(ALICE), PrivatePlayerData(ALICE)))


def test_internal_state_rejects_wrong_data_layers_and_unknown_private_owner() -> None:
    with pytest.raises(TypeError, match="public"):
        GameState(SESSION, "big_two", "1", cast(PublicGameData, {}), PrivateGameData())
    with pytest.raises(TypeError, match="private"):
        GameState(SESSION, "big_two", "1", public_data(), cast(PrivateGameData, {}))
    with pytest.raises(ValueError, match="private player"):
        GameState(
            SESSION, "big_two", "1", public_data(), PrivateGameData((PrivatePlayerData(OTHER),))
        )


def test_view_accepts_only_the_viewers_single_private_data() -> None:
    public = public_data()
    with pytest.raises(ValueError, match="belong to the viewer"):
        PlayerView(ALICE, public, PrivatePlayerData(BOB))
    with pytest.raises(ValueError, match="belong to the game"):
        PlayerView(OTHER, public, PrivatePlayerData(OTHER))
    with pytest.raises(TypeError, match="private"):
        PlayerView(ALICE, public, cast(PrivatePlayerData, PrivateGameData()))
    with pytest.raises(TypeError, match="public"):
        PlayerView(ALICE, cast(PublicGameData, {}), PrivatePlayerData(ALICE))


def test_public_structure_is_an_explicit_whitelist_without_hidden_data() -> None:
    assert {item.name for item in fields(PublicGameData)} == {
        "status",
        "state_version",
        "players",
        "turn",
    }
    assert {item.name for item in fields(Player)} == {"id", "display_name", "seat", "points"}
    serialized = repr(asdict(public_data()))
    for forbidden in ("hand", "remaining_cards", "private", "deck", "payload"):
        assert forbidden not in serialized
    with pytest.raises(TypeError):
        cast(Callable[..., PublicGameData], PublicGameData)(
            GameStatus.WAITING, 0, (), hand=(Card.from_code("AS"),)
        )
    with pytest.raises(TypeError):
        PublicGameData(GameStatus.WAITING, 0, cast(tuple[Player, ...], (PrivatePlayerData(ALICE),)))


def test_repr_hides_private_hands_and_remaining_cards() -> None:
    private = PrivatePlayerData(ALICE, (Card.from_code("AS"),))
    hidden = PrivateGameData((private,), (Card.from_code("KH"),))
    state = GameState(SESSION, "texas_holdem", "1", public_data(), hidden)
    view = PlayerView(ALICE, public_data(), private)
    for model in (private, hidden, state, view):
        assert "Card(" not in repr(model)
        assert "hand=" not in repr(model)
        assert "remaining_cards=" not in repr(model)


def test_models_do_not_generate_ids_deal_or_shuffle(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("pure model unexpectedly executed a game operation")

    monkeypatch.setattr(Deck, "__init__", forbidden)
    monkeypatch.setattr(Deck, "deal", forbidden)
    monkeypatch.setattr(Deck, "shuffle", forbidden)
    monkeypatch.setattr("uuid.uuid4", forbidden)
    public = public_data()
    state = GameState(SESSION, "big_two", "1", public, PrivateGameData())
    assert state.session_id == SESSION
    assert GameAction(ALICE, REQUEST, 12, "custom_game_action").type == "custom_game_action"
    assert public.state_version == 12


def test_models_are_frozen_and_replace_revalidates() -> None:
    player = roster()[0]
    with pytest.raises(FrozenInstanceError):
        cast(Any, player).points = 999
    with pytest.raises(ValueError):
        replace(player, points=-1)
    with pytest.raises(TypeError):
        replace(public_data(), status=cast(GameStatus, "invalid"))


@pytest.mark.parametrize("order", list(itertools.permutations(("models", "card", "deck"))))
def test_import_orders_have_no_cycles_or_framework_dependencies(order: tuple[str, ...]) -> None:
    code = (
        "import importlib,json,sys; "
        "[importlib.import_module('app.games.core.'+name) for name in sys.argv[1:]]; "
        "print(json.dumps([name for name in ('fastapi','sqlalchemy','pydantic') "
        "if name in sys.modules]))"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, *order],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == []
    assert importlib.import_module("app.games.core.models").PlayerId.__value__ is UUID
