"""P2-C GameEngine contract: a Protocol only. No game, registry or transport.

Rules for every engine:
- Pure and deterministic except create_game, the only place randomness (the
  injected production Deck) is consumed. No FastAPI/SQLAlchemy/React imports.
- Expected rejections (illegal action, stale version, bad player set) are returned
  as GameError data; exceptions are reserved for programming errors.
- validate_action and get_player_view never change their inputs.
- apply_action returns a new state with state_version + 1 and consecutive events.
- get_player_view must rebuild the view from GameState and expose only the
  viewer's own private data, never other hands or remaining cards. The caller
  supplies an authenticated viewer_id; this contract is not an authorization check.
- Action payloads are engine-specific (PayloadT); GameAction itself is unchanged and
  no arbitrary dict is accepted.
"""

from typing import Protocol
from uuid import UUID

from app.games.core.deck import Deck, DeckUnavailableError
from app.games.core.engine_types import (
    ActionValidation,
    ApplyResult,
    GameConfig,
    GameResult,
)
from app.games.core.models import (
    GameAction,
    GameError,
    GameState,
    Player,
    PlayerId,
    PlayerView,
)

FULL_DECK_SIZE = 52


class TestOnlyDeckError(ValueError):
    """A fixed-order or otherwise non-production deck was supplied to an engine."""

    __test__ = False  # not a pytest class despite the name


def require_production_deck(deck: object) -> Deck:
    """Gate for create_game implementations; guards against misuse, not tampering.

    Accepts only an exact, available, unused, securely shuffled Deck. Client-provided card
    orders never reach this point because engines never accept them.
    """
    if type(deck) is not Deck:
        raise TypeError("deck must be an exact Deck instance")
    if deck.is_test_only:
        raise TestOnlyDeckError("test-only decks are not accepted by engines")
    if not deck.is_available:
        raise DeckUnavailableError("deck is unavailable after a failed secure shuffle")
    if deck.remaining_count != FULL_DECK_SIZE:
        raise ValueError("engines require a complete, undealt deck")
    return deck


class GameEngine[PayloadT](Protocol):
    def create_game(
        self,
        config: GameConfig,
        session_id: UUID,
        players: tuple[Player, ...],
        deck: Deck,
    ) -> GameState | GameError: ...

    def validate_action(
        self, state: GameState, action: GameAction, payload: PayloadT
    ) -> ActionValidation: ...

    def apply_action(
        self, state: GameState, action: GameAction, payload: PayloadT
    ) -> ApplyResult | GameError: ...

    def get_player_view(self, state: GameState, viewer_id: PlayerId) -> PlayerView | GameError: ...

    def is_game_over(self, state: GameState) -> bool: ...

    def calculate_result(self, state: GameState) -> GameResult | GameError: ...
