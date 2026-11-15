"""P2-F: private-information projection helpers (not an authorization boundary)."""

from dataclasses import asdict
from typing import Any, cast
from uuid import UUID

import pytest

from app.games.core import (
    NOT_IN_GAME,
    Card,
    EventVisibility,
    GameError,
    GameEvent,
    GameState,
    GameStatus,
    Player,
    PlayerView,
    PrivateGameData,
    PrivatePlayerData,
    PublicGameData,
    Turn,
    events_for_viewer,
    project_player_view,
)

ALICE, BOB, CAROL, OUTSIDER, SESSION = (UUID(int=n) for n in (1, 2, 3, 9, 100))
ALICE_HAND = (Card.from_code("AS"), Card.from_code("KS"))
BOB_HAND = (Card.from_code("2C"), Card.from_code("3C"))
CAROL_HAND = (Card.from_code("7H"), Card.from_code("8H"))
REMAINING = (Card.from_code("QD"), Card.from_code("JD"))
MARKER = "PROJECTION_SECRET_3v"


class UuidWithSecret(UUID):
    secret = MARKER


class TupleWithSecret(tuple):  # type: ignore[type-arg]
    secret = MARKER


def state(with_private: bool = True) -> GameState:
    players = (Player(ALICE, "Alice", 0), Player(BOB, "Bob", 1), Player(CAROL, "Carol", 2))
    private = (
        PrivateGameData(
            (
                PrivatePlayerData(ALICE, ALICE_HAND),
                PrivatePlayerData(BOB, BOB_HAND),
                PrivatePlayerData(CAROL, CAROL_HAND),
            ),
            REMAINING,
        )
        if with_private
        else PrivateGameData()
    )
    return GameState(
        SESSION, "stub", "1", PublicGameData(GameStatus.IN_PROGRESS, 4, players, Turn(BOB)), private
    )


def test_view_contains_public_data_and_only_the_viewers_hand() -> None:
    game = state()
    for viewer, hand in ((ALICE, ALICE_HAND), (BOB, BOB_HAND), (CAROL, CAROL_HAND)):
        view = project_player_view(game, viewer)
        assert isinstance(view, PlayerView)
        assert view.viewer_id == viewer and view.private.player_id == viewer
        assert view.private.hand == hand
        assert view.public == game.public
        text = repr(asdict(view.public)) + repr(view.public)
        for card in (*ALICE_HAND, *BOB_HAND, *CAROL_HAND, *REMAINING):
            assert card.code not in text and repr(card) not in text


def test_other_players_hands_and_remaining_cards_never_reach_the_view() -> None:
    view = project_player_view(state(), ALICE)
    assert isinstance(view, PlayerView)
    leaked = repr(view) + repr(asdict(view.public)) + repr(asdict(view.private))
    for card in (*BOB_HAND, *CAROL_HAND, *REMAINING):
        assert repr(card) not in leaked
    assert all(card not in (*BOB_HAND, *CAROL_HAND, *REMAINING) for card in view.private.hand)


def test_view_is_rebuilt_not_reused_and_input_is_unchanged() -> None:
    game = state()
    before = repr(asdict(game))
    view = project_player_view(game, ALICE)
    assert isinstance(view, PlayerView)
    assert view.public is not game.public and view.public == game.public
    assert view.public.players is game.public.players  # immutable tuple reuse is fine
    assert repr(asdict(game)) == before


def test_member_without_private_entry_gets_an_empty_hand() -> None:
    view = project_player_view(state(with_private=False), ALICE)
    assert isinstance(view, PlayerView) and view.private.hand == ()


@pytest.mark.parametrize("viewer", [OUTSIDER, UUID(int=0)])
def test_non_members_get_a_game_error_without_echoing_the_id(viewer: UUID) -> None:
    error = project_player_view(state(), viewer)
    assert isinstance(error, GameError) and error.code == NOT_IN_GAME
    assert str(viewer) not in error.message


@pytest.mark.parametrize("viewer", [None, str(ALICE), 1, UuidWithSecret(int=1)])
def test_viewer_id_must_be_an_exact_uuid(viewer: object) -> None:
    with pytest.raises(TypeError, match="viewer_id must be a UUID"):
        project_player_view(state(), cast(UUID, viewer))
    with pytest.raises(TypeError, match="viewer_id must be a UUID"):
        events_for_viewer((), cast(UUID, viewer))


def test_state_must_be_an_exact_game_state() -> None:
    for bad in (None, {"public": 1}, object()):
        with pytest.raises(TypeError, match="exact GameState"):
            project_player_view(cast(GameState, bad), ALICE)


def test_state_altered_after_construction_is_revalidated_at_projection() -> None:
    class NameWithHand(str):
        hand = ALICE_HAND

    game = state()
    tampered = object.__new__(Player)
    for key, value in {
        "id": ALICE,
        "display_name": NameWithHand("x"),
        "seat": 0,
        "points": 0,
    }.items():
        object.__setattr__(tampered, key, value)
    object.__setattr__(game.public, "players", (tampered, *game.public.players[1:]))
    with pytest.raises(TypeError, match="display_name must be a string"):
        project_player_view(game, ALICE)


# ---- events ---------------------------------------------------------------


def events() -> tuple[GameEvent, ...]:
    return (
        GameEvent(1, "dealt", EventVisibility.PRIVATE, ALICE),
        GameEvent(2, "dealt", EventVisibility.PRIVATE, BOB),
        GameEvent(3, "bet", EventVisibility.PUBLIC),
        GameEvent(4, "peek", EventVisibility.PRIVATE, ALICE),
    )


def test_events_include_public_and_own_private_only_in_order() -> None:
    all_events = events()
    assert [e.seq for e in events_for_viewer(all_events, ALICE)] == [1, 3, 4]
    assert [e.seq for e in events_for_viewer(all_events, BOB)] == [2, 3]
    assert [e.seq for e in events_for_viewer(all_events, CAROL)] == [3]
    assert [e.seq for e in events_for_viewer(all_events, OUTSIDER)] == [3]
    assert all(e.recipient_id in (None, BOB) for e in events_for_viewer(all_events, BOB))


def test_events_helper_does_not_mutate_and_handles_empty() -> None:
    all_events = events()
    result = events_for_viewer(all_events, ALICE)
    assert all_events == events() and isinstance(result, tuple)
    assert events_for_viewer((), ALICE) == ()


def test_events_reject_invalid_containers_and_subclass_elements() -> None:
    from dataclasses import dataclass

    @dataclass(frozen=True, slots=True)
    class EventWithHand(GameEvent):
        hand: tuple[Card, ...] = ()

    good = events()
    with pytest.raises(TypeError, match="events must be a tuple"):
        events_for_viewer(cast(Any, list(good)), ALICE)
    with pytest.raises(TypeError, match="events must be a tuple"):
        events_for_viewer(cast(Any, TupleWithSecret(good)), ALICE)
    with pytest.raises(TypeError, match="invalid element"):
        events_for_viewer(cast(Any, (*good, None)), ALICE)
    with pytest.raises(TypeError, match="exact GameEvent"):
        events_for_viewer((EventWithHand(5, "x", EventVisibility.PUBLIC, hand=ALICE_HAND),), ALICE)
