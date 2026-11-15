"""P2-D in-memory engine registry. No game, database, transport or global instance.

Contract:
- EngineRegistry is an ordinary instance; the future composition layer creates one at
  startup and registers engines then. Registration is not thread-safe; treat the
  registry as read-only after startup.
- Expected rejections (duplicate or unknown code) are returned as GameError; a
  malformed registration (bad code, player range, non-engine object) raises, since
  that is a programming error. Unknown codes are never echoed into messages.
- The registry does not store an "enabled" flag and does not read the database.
  A game is playable only when the database says enabled AND the registry has an
  engine; the composition layer owns that intersection. An unimplemented game is
  simply not registered, so it cannot be looked up.
- Runtime engine check confirms only that the six methods exist and are callable,
  not their signatures or semantics; semantics need a shared contract suite.
"""

import re
from dataclasses import dataclass
from typing import Any

from app.games.core.engine import GameEngine
from app.games.core.models import (
    GameError,
    _exact_type,
    _nonnegative_int,
    _text,
)

ENGINE_METHODS = (
    "create_game",
    "validate_action",
    "apply_action",
    "get_player_view",
    "is_game_over",
    "calculate_result",
)

# Matches the game_types.code column (String(32)); lowercase snake_case.
_CODE_PATTERN = re.compile(r"[a-z][a-z0-9_]{1,31}")

DUPLICATE_GAME = "duplicate_game"
UNKNOWN_GAME = "unknown_game"


def _game_code(value: str) -> None:
    _text(value, "game code")
    if _CODE_PATTERN.fullmatch(value) is None:
        raise ValueError("game code must be 2-32 lowercase letters, digits or underscores")


@dataclass(frozen=True, slots=True)
class EngineRegistration:
    """One registered engine plus its versioned metadata."""

    code: str
    rules_version: str
    min_players: int
    max_players: int
    engine: GameEngine[Any]

    def __post_init__(self) -> None:
        _game_code(self.code)
        _text(self.rules_version, "rules_version")
        _nonnegative_int(self.min_players, "min_players")
        _nonnegative_int(self.max_players, "max_players")
        if self.min_players < 2:
            raise ValueError("min_players must be at least 2")
        if self.max_players < self.min_players:
            raise ValueError("max_players cannot be below min_players")
        if isinstance(self.engine, type):
            raise TypeError("engine must be an instance, not a class")
        for name in ENGINE_METHODS:
            if not callable(getattr(self.engine, name, None)):
                raise TypeError(f"engine is missing a callable {name}")


class EngineRegistry:
    """Mutable only through register(); lookups return immutable snapshots."""

    __slots__ = ("_entries",)

    def __init__(self) -> None:
        self._entries: dict[str, EngineRegistration] = {}

    def register(self, registration: EngineRegistration) -> GameError | None:
        _exact_type(registration, EngineRegistration, "registration")
        if registration.code in self._entries:
            return GameError(DUPLICATE_GAME, "A game with this code is already registered")
        self._entries[registration.code] = registration
        return None

    def get(self, code: str) -> EngineRegistration | GameError:
        _game_code_type(code)
        entry = self._entries.get(code)
        if entry is None:
            return GameError(UNKNOWN_GAME, "Unknown game")
        return entry

    def is_registered(self, code: str) -> bool:
        _game_code_type(code)
        return code in self._entries

    def codes(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def registrations(self) -> tuple[EngineRegistration, ...]:
        return tuple(self._entries[code] for code in self.codes())

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:
        return f"EngineRegistry(codes={self.codes()!r})"


def _game_code_type(code: object) -> None:
    """Lookups accept any well-typed str (client text may be arbitrary); wrong types raise."""
    if type(code) is not str:
        raise TypeError("game code must be a string")
