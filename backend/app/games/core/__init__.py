"""Card/deck primitives and internal data types; no game engines implemented."""

from app.games.core.card import Card, Rank, Suit
from app.games.core.deck import Deck, InsufficientCardsError
from app.games.core.engine import (
    GameEngine,
    TestOnlyDeckError,
    require_production_deck,
)
from app.games.core.engine_types import (
    ActionValidation,
    ApplyResult,
    EventVisibility,
    GameConfig,
    GameEvent,
    GameResult,
    PlayerResult,
)
from app.games.core.models import (
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
from app.games.core.registry import (
    DUPLICATE_GAME,
    ENGINE_METHODS,
    UNKNOWN_GAME,
    EngineRegistration,
    EngineRegistry,
)

__all__ = [
    "DUPLICATE_GAME",
    "ENGINE_METHODS",
    "UNKNOWN_GAME",
    "EngineRegistration",
    "EngineRegistry",
    "ActionValidation",
    "ApplyResult",
    "EventVisibility",
    "GameConfig",
    "GameEngine",
    "GameEvent",
    "GameResult",
    "PlayerResult",
    "TestOnlyDeckError",
    "require_production_deck",
    "Card",
    "Deck",
    "GameAction",
    "GameError",
    "GameState",
    "GameStatus",
    "InsufficientCardsError",
    "Player",
    "PlayerId",
    "PlayerView",
    "PrivateGameData",
    "PrivatePlayerData",
    "PublicGameData",
    "Rank",
    "Suit",
    "Turn",
]
