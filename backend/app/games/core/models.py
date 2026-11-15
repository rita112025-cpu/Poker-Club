"""P2-B internal data contracts, independent of engines, transport and persistence.

These classes validate structure, not game legality or lifecycle transitions.
Never serialize GameState wholesale for a client. PlayerView has an explicit
viewer and exactly that player's private data; constructing it performs no
projection, dealing, authentication or authorization.
"""

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID

from app.games.core.card import Card
from app.games.core.extensions import PublicExtension, check_public_extension

type PlayerId = UUID


# Every model field value is checked with `type(value) is X`, never isinstance:
# a subclass of str/UUID/tuple/Player/... can carry extra attributes that
# asdict()/deepcopy()/repr() would retain. Rejection is by exact type, with no
# conversion; this is not a Python security sandbox.


def _uuid(value: object, name: str) -> None:
    if type(value) is not UUID:
        raise TypeError(f"{name} must be a UUID")


def _text(value: object, name: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} cannot be blank")


def _nonnegative_int(value: object, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} cannot be negative")


def _tuple_of(value: object, expected: type[object], name: str) -> None:
    if type(value) is not tuple:
        raise TypeError(f"{name} must be a tuple")
    if any(not isinstance(item, expected) for item in value):
        raise TypeError(f"{name} contains an invalid element")


def _exact_type(value: object, expected: type[object], name: str) -> None:
    if type(value) is not expected:
        raise TypeError(
            f"{name} must be an exact {expected.__name__} instance; subclasses are not allowed"
        )


def _cards(value: object, name: str) -> None:
    _tuple_of(value, Card, name)
    if isinstance(value, tuple) and len(set(value)) != len(value):
        raise ValueError(f"{name} cannot contain duplicate cards")


def _check_status(value: object) -> None:
    if type(value) is not GameStatus:
        raise TypeError("status must be a GameStatus member")


def _check_public_player(player: "Player") -> None:
    """Re-validate every Player field at the public boundary, not only at Player creation."""
    _exact_type(player, Player, "public player")
    _uuid(player.id, "player id")
    _text(player.display_name, "display_name")
    _nonnegative_int(player.seat, "seat")
    _nonnegative_int(player.points, "points")


class GameStatus(Enum):
    """Minimal game lifecycle; streets and other game-specific phases are separate."""

    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"


@dataclass(frozen=True, slots=True)
class Player:
    """Public player data. id refers to a user identity, not a game_players row id."""

    id: PlayerId
    display_name: str
    seat: int
    points: int = 0

    def __post_init__(self) -> None:
        _uuid(self.id, "player id")
        _text(self.display_name, "display_name")
        _nonnegative_int(self.seat, "seat")
        _nonnegative_int(self.points, "points")


@dataclass(frozen=True, slots=True)
class Turn:
    """The current actor only; no timer, next-player selection or mutation."""

    player_id: PlayerId

    def __post_init__(self) -> None:
        _uuid(self.player_id, "turn player_id")


@dataclass(frozen=True, slots=True)
class GameAction:
    """Server-bound action metadata, not a WS decoder or a legal-action validator.

    player_id must come from authenticated server context. type is extensible;
    game-specific payloads and legality belong to later game implementations.
    No arbitrary dict payload or caller-provided deck/result is accepted here.
    """

    player_id: PlayerId
    request_id: UUID
    state_version: int
    type: str

    def __post_init__(self) -> None:
        _uuid(self.player_id, "action player_id")
        _uuid(self.request_id, "request_id")
        _nonnegative_int(self.state_version, "state_version")
        _text(self.type, "action type")


@dataclass(frozen=True, slots=True)
class GameError:
    """Error data, not an exception or HTTP response. message must be safe to expose."""

    code: str
    message: str
    request_id: UUID | None = None

    def __post_init__(self) -> None:
        _text(self.code, "error code")
        _text(self.message, "error message")
        if self.request_id is not None:
            _uuid(self.request_id, "request_id")


@dataclass(frozen=True, slots=True)
class PublicGameData:
    """Public schema with exact Player/Turn types; subclasses are not public DTOs.

    Reject extended models instead of preserving or implicitly converting fields
    that could contain private data. This is not a Python security sandbox.
    """

    status: GameStatus
    state_version: int
    players: tuple[Player, ...]
    turn: Turn | None = None

    def __post_init__(self) -> None:
        _exact_type(self, PublicGameData, "public")
        _check_status(self.status)
        _nonnegative_int(self.state_version, "state_version")
        _tuple_of(self.players, Player, "players")
        for player in self.players:
            _check_public_player(player)
        identities = {player.id for player in self.players}
        if len(identities) != len(self.players):
            raise ValueError("players cannot contain duplicate identities")
        if len({player.seat for player in self.players}) != len(self.players):
            raise ValueError("players cannot share a seat")
        if self.turn is not None:
            _exact_type(self.turn, Turn, "public turn")
            _uuid(self.turn.player_id, "turn player_id")
            if self.turn.player_id not in identities:
                raise ValueError("turn player must belong to the game")


@dataclass(frozen=True, slots=True)
class PrivatePlayerData:
    """One player's hidden cards; not included in public data or repr."""

    player_id: PlayerId
    hand: tuple[Card, ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        _uuid(self.player_id, "private player_id")
        _cards(self.hand, "hand")


@dataclass(frozen=True, slots=True)
class PrivateGameData:
    """Server-only snapshot data, not a mutable Deck or an event-replay mechanism."""

    players: tuple[PrivatePlayerData, ...] = field(default=(), repr=False)
    remaining_cards: tuple[Card, ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        _tuple_of(self.players, PrivatePlayerData, "private players")
        if len({player.player_id for player in self.players}) != len(self.players):
            raise ValueError("private players cannot contain duplicate identities")
        _cards(self.remaining_cards, "remaining_cards")


@dataclass(frozen=True, slots=True)
class GameState:
    """Internal state container. Constructing it has no execution or persistence effects."""

    session_id: UUID
    game_type: str
    rules_version: str
    public: PublicGameData
    private: PrivateGameData = field(repr=False)
    extension: PublicExtension | None = None

    def __post_init__(self) -> None:
        check_public_extension(self.extension, "extension")
        _uuid(self.session_id, "session_id")
        _text(self.game_type, "game_type")
        _text(self.rules_version, "rules_version")
        _exact_type(self.public, PublicGameData, "public")
        if not isinstance(self.private, PrivateGameData):
            raise TypeError("private must be PrivateGameData")
        identities = {player.id for player in self.public.players}
        if any(player.player_id not in identities for player in self.private.players):
            raise ValueError("private player must belong to the game")


@dataclass(frozen=True, slots=True)
class PlayerView:
    """A data container for public data plus a single viewer's own private data.

    The future server must supply the authenticated viewer_id. This validation
    checks internal consistency only and is not an authorization boundary.
    """

    viewer_id: PlayerId
    public: PublicGameData
    private: PrivatePlayerData = field(repr=False)
    extension: PublicExtension | None = None

    def __post_init__(self) -> None:
        check_public_extension(self.extension, "extension")
        _uuid(self.viewer_id, "viewer_id")
        _exact_type(self.public, PublicGameData, "public")
        if not isinstance(self.private, PrivatePlayerData):
            raise TypeError("private must be PrivatePlayerData")
        if self.private.player_id != self.viewer_id:
            raise ValueError("private data must belong to the viewer")
        if self.viewer_id not in {player.id for player in self.public.players}:
            raise ValueError("viewer must belong to the game")
