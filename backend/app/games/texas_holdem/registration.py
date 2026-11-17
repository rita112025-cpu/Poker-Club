"""Registering the Texas hold'em engine with an EngineRegistry (P3-05).

The registration code, the player range and the rules version are fixed here or taken from
the rules object; nothing is registered by default and nothing is hard-coded elsewhere: the
composition root that owns an EngineRegistry calls register_texas_holdem with the APPROVED
rules. Those rule values (blinds, burn setting, chip unit) are still an open policy decision,
so this module deliberately offers no default rules.
"""

from app.games.core.models import GameError
from app.games.core.registry import EngineRegistration, EngineRegistry
from app.games.core.validation import require_exact
from app.games.texas_holdem.engine import TexasEngine
from app.games.texas_holdem.hand import GAME_TYPE
from app.games.texas_holdem.positions import MAX_PLAYERS, MIN_PLAYERS
from app.games.texas_holdem.rules import TexasRules

TEXAS_CODE = GAME_TYPE  # "texas_holdem": the code of the game_types catalog row


def texas_registration(rules: TexasRules) -> EngineRegistration:
    """The registration record for a Texas engine playing under `rules`."""
    require_exact(rules, TexasRules, "rules")
    return EngineRegistration(
        TEXAS_CODE, rules.version, MIN_PLAYERS, MAX_PLAYERS, TexasEngine(rules)
    )


def register_texas_holdem(registry: EngineRegistry, rules: TexasRules) -> GameError | None:
    """Register the engine; a duplicate comes back as a GameError (callers MUST check it)."""
    return registry.register(texas_registration(rules))
