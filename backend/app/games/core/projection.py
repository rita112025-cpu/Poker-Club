"""P2-F private-information projection helpers: pure, default building blocks for engines.

These are NOT an authorization boundary: the caller must supply an authenticated
viewer_id. They suit engines whose only private data is per-player hands; engines
that expose extra public facts (e.g. opponent card counts) implement their own
get_player_view, which this module does not decide.

Projection rebuilds the public and private structures from the GameState fields, so
the exact-type validation runs again on every field (it also catches a state whose
public data was altered after construction). Nothing from the input is reused as a
view, and other players' hands and the remaining cards are never read into the result.
"""

from app.games.core.card import Card
from app.games.core.engine_types import EventVisibility, GameEvent
from app.games.core.models import (
    GameError,
    GameState,
    PlayerId,
    PlayerView,
    PrivatePlayerData,
    PublicGameData,
    _exact_type,
    _tuple_of,
    _uuid,
)

NOT_IN_GAME = "not_in_game"


def project_player_view(state: GameState, viewer_id: PlayerId) -> PlayerView | GameError:
    """Public data plus only the viewer's own hand; non-members get a GameError."""
    _exact_type(state, GameState, "state")
    _uuid(viewer_id, "viewer_id")
    public = state.public
    if viewer_id not in {player.id for player in public.players}:
        return GameError(NOT_IN_GAME, "Viewer is not in this game")
    rebuilt = PublicGameData(public.status, public.state_version, public.players, public.turn)
    hand: tuple[Card, ...] = ()
    for item in state.private.players:
        if item.player_id == viewer_id:
            hand = item.hand
            break
    return PlayerView(viewer_id, rebuilt, PrivatePlayerData(viewer_id, hand))


def events_for_viewer(events: tuple[GameEvent, ...], viewer_id: PlayerId) -> tuple[GameEvent, ...]:
    """Public events plus private events addressed to the viewer, in the original order."""
    _tuple_of(events, GameEvent, "events")
    for event in events:
        _exact_type(event, GameEvent, "event")
    _uuid(viewer_id, "viewer_id")
    return tuple(
        event
        for event in events
        if event.visibility is EventVisibility.PUBLIC or event.recipient_id == viewer_id
    )
