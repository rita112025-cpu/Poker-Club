"""Versioned Texas hold'em table rules (P3-01). No product defaults are defined here:
blind sizes, starting points and burning are provided by the caller and recorded in the
rules version, because changing any of them changes game outcomes and replays.
"""

from dataclasses import dataclass

from app.games.core.validation import require_bool, require_int, require_text


@dataclass(frozen=True, slots=True)
class TexasRules:
    version: str
    small_blind: int
    big_blind: int
    # Whether one card is burned before the flop, turn and river (acts from P3-02 on).
    burn_cards: bool

    def __post_init__(self) -> None:
        require_text(self.version, "rules version")
        require_int(self.small_blind, "small_blind")
        require_int(self.big_blind, "big_blind")
        require_bool(self.burn_cards, "burn_cards")
        if self.small_blind < 1:
            raise ValueError("small_blind must be at least 1")
        if self.big_blind < self.small_blind:
            raise ValueError("big_blind cannot be below small_blind")
