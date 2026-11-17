"""Composition root for the prototype: builds an EngineRegistry and registers hold'em.

The rules come from Settings and are prototype values, not approved policy. The engine is
obtained from the Registry, never constructed here.
"""

from app.core.config import Settings
from app.games.core import EngineRegistry
from app.games.texas_holdem import TEXAS_CODE, TexasEngine, TexasRules, register_texas_holdem

PROTOTYPE_RULES_VERSION = "prototype-1"


def prototype_rules(settings: Settings) -> TexasRules:
    return TexasRules(
        PROTOTYPE_RULES_VERSION,
        settings.prototype_small_blind,
        settings.prototype_big_blind,
        settings.prototype_burn_cards,
    )


def build_texas_engine(settings: Settings) -> tuple[TexasEngine, TexasRules]:
    registry = EngineRegistry()
    rules = prototype_rules(settings)
    error = register_texas_holdem(registry, rules)
    if error is not None:
        raise RuntimeError(error.code)
    entry = registry.get(TEXAS_CODE)
    if not hasattr(entry, "engine") or not isinstance(entry.engine, TexasEngine):
        raise RuntimeError("texas_holdem is not registered")
    return entry.engine, rules
