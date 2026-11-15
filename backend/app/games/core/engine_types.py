"""P2-C engine result types: pure data, validated by exact type, no behaviour.

Public field matrix (exact type; validation entry is each __post_init__):
  GameConfig.game_type/rules_version str | EventVisibility member
  GameEvent.seq int>=0 | event_type str | visibility EventVisibility | recipient_id UUID | None
  ActionValidation.error GameError | None
  ApplyResult.state GameState | events tuple[GameEvent, ...] (contiguous seq, private
      recipients must be players of the state)
  PlayerResult.player_id UUID | points_delta int (signed) | rank int>=1
  GameResult.players tuple[PlayerResult, ...] (unique ids, deltas sum to zero)

Same trust model as P2-B: validation at construction only, not a Python sandbox.
Events carry metadata only; game-specific payloads belong to each future engine,
and a PRIVATE event must never be broadcast to anyone but its recipient.
"""

from dataclasses import dataclass
from enum import Enum

from app.games.core.extensions import EventPayload, check_event_payload

# Reuse the P2-B exact-type validators so both modules share one rule set.
from app.games.core.models import (
    GameError,
    GameState,
    PlayerId,
    _exact_type,
    _nonnegative_int,
    _text,
    _tuple_of,
    _uuid,
)


def _signed_int(value: object, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")


class EventVisibility(Enum):
    PUBLIC = "public"
    PRIVATE = "private"


@dataclass(frozen=True, slots=True)
class GameConfig:
    """Versioned engine configuration; rules_version is stored with every session."""

    game_type: str
    rules_version: str

    def __post_init__(self) -> None:
        _text(self.game_type, "game_type")
        _text(self.rules_version, "rules_version")


@dataclass(frozen=True, slots=True)
class GameEvent:
    """Ordered event metadata. PUBLIC has no recipient; PRIVATE has exactly one."""

    seq: int
    event_type: str
    visibility: EventVisibility
    recipient_id: PlayerId | None = None
    payload: EventPayload | None = None

    def __post_init__(self) -> None:
        check_event_payload(self.payload, "event payload")
        _nonnegative_int(self.seq, "event seq")
        _text(self.event_type, "event_type")
        if type(self.visibility) is not EventVisibility:
            raise TypeError("visibility must be an EventVisibility member")
        if self.visibility is EventVisibility.PUBLIC:
            if self.recipient_id is not None:
                raise ValueError("public events cannot have a recipient")
        else:
            _uuid(self.recipient_id, "event recipient_id")


@dataclass(frozen=True, slots=True)
class ActionValidation:
    """Outcome of validate_action: valid when there is no error."""

    error: GameError | None = None

    def __post_init__(self) -> None:
        if self.error is not None:
            _exact_type(self.error, GameError, "validation error")

    @property
    def is_valid(self) -> bool:
        return self.error is None


@dataclass(frozen=True, slots=True)
class ApplyResult:
    """New state plus its ordered events; seq values are consecutive."""

    state: GameState
    events: tuple[GameEvent, ...] = ()

    def __post_init__(self) -> None:
        _exact_type(self.state, GameState, "state")
        _tuple_of(self.events, GameEvent, "events")
        for event in self.events:
            _exact_type(event, GameEvent, "event")
        for previous, current in zip(self.events, self.events[1:], strict=False):
            if current.seq != previous.seq + 1:
                raise ValueError("event seq values must be consecutive")
        members = {player.id for player in self.state.public.players}
        for event in self.events:
            if event.recipient_id is not None and event.recipient_id not in members:
                raise ValueError("event recipient must belong to the game")


@dataclass(frozen=True, slots=True)
class PlayerResult:
    player_id: PlayerId
    points_delta: int
    rank: int

    def __post_init__(self) -> None:
        _uuid(self.player_id, "result player_id")
        _signed_int(self.points_delta, "points_delta")
        _nonnegative_int(self.rank, "rank")
        if self.rank < 1:
            raise ValueError("rank must be at least 1")


@dataclass(frozen=True, slots=True)
class GameResult:
    """Per-player outcome only; no hand evaluation. Points are conserved (sum zero)."""

    players: tuple[PlayerResult, ...]

    def __post_init__(self) -> None:
        _tuple_of(self.players, PlayerResult, "result players")
        for player in self.players:
            _exact_type(player, PlayerResult, "result player")
        if not self.players:
            raise ValueError("result must include at least one player")
        if len({player.player_id for player in self.players}) != len(self.players):
            raise ValueError("result players cannot contain duplicate identities")
        if sum(player.points_delta for player in self.players) != 0:
            raise ValueError("points must be conserved; deltas must sum to zero")
