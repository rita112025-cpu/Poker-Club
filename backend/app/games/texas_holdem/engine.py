"""TexasEngine (P3-02): the six GameEngine methods for fold/check/call hands.

Not registered anywhere yet (Registry integration is P3-05). calculate_result reports
"not implemented" until settlement exists (P3-04). Expected rejections are GameError data
and never echo cards. A fixed-order deck can only enter through create_game_for_testing,
which no application module may call (static guard test).
"""

from dataclasses import dataclass, replace
from uuid import UUID

from app.games.core.deck import Deck
from app.games.core.engine_types import (
    ActionValidation,
    ApplyResult,
    EventVisibility,
    GameConfig,
    GameEvent,
    GameResult,
)
from app.games.core.models import (
    GameAction,
    GameError,
    GameState,
    GameStatus,
    Player,
    PlayerId,
    PlayerView,
)
from app.games.core.projection import project_player_view
from app.games.core.validation import require_exact, require_nonnegative_int
from app.games.texas_holdem.betting import (
    ALL_IN,
    CHECK,
    FOLD,
    KNOWN_ACTIONS,
    UNSUPPORTED_ACTIONS,
    advance,
    amount_to_call,
    legal_actions,
    seat_to_act,
)
from app.games.texas_holdem.events import ActionTaken
from app.games.texas_holdem.hand import GAME_TYPE, start_hand, start_hand_for_testing
from app.games.texas_holdem.rules import TexasRules
from app.games.texas_holdem.state import HandEnd, TexasPublic

CONFIG_MISMATCH = "config_mismatch"
WRONG_GAME = "wrong_game"
GAME_OVER = "game_over"
STALE_STATE = "stale_state"
NOT_YOUR_TURN = "not_your_turn"
UNKNOWN_ACTION = "unknown_action"
BAD_PAYLOAD = "bad_payload"
ILLEGAL_ACTION = "illegal_action"
NOT_SUPPORTED_YET = "not_supported_yet"
NOT_FINISHED = "not_finished"
NOT_IMPLEMENTED = "not_implemented"


@dataclass(frozen=True, slots=True)
class TexasPayload:
    """Action payload; amount is for bet/raise (P3-03) and must be None for the rest."""

    amount: int | None = None

    def __post_init__(self) -> None:
        if self.amount is not None:
            require_nonnegative_int(self.amount, "amount")


class TexasEngine:
    def __init__(self, rules: TexasRules) -> None:
        require_exact(rules, TexasRules, "rules")
        self._rules = rules

    # -- creation ------------------------------------------------------------------

    def _mismatch(self, config: GameConfig) -> GameError | None:
        if config.game_type != GAME_TYPE or config.rules_version != self._rules.version:
            return GameError(CONFIG_MISMATCH, "The configuration does not match this engine")
        return None

    def _normalise(self, created: GameState | GameError) -> GameState | GameError:
        """If nobody can act at the start (everyone all-in), deal the board out now."""
        if isinstance(created, GameError) or created.public.turn is not None:
            return created
        table = created.extension
        if not isinstance(table, TexasPublic):
            return created
        return advance(created, table, self._rules.burn_cards, None, [])[0]

    def create_game(
        self,
        config: GameConfig,
        session_id: UUID,
        players: tuple[Player, ...],
        deck: Deck,
    ) -> GameState | GameError:
        error = self._mismatch(config)
        if error is not None:
            return error
        return self._normalise(start_hand(self._rules, session_id, players, deck))

    def create_game_for_testing(
        self,
        config: GameConfig,
        session_id: UUID,
        players: tuple[Player, ...],
        deck: Deck,
        button_seat: int | None = None,
    ) -> GameState | GameError:
        """Trusted tests only: accepts a fixed-order deck."""
        error = self._mismatch(config)
        if error is not None:
            return error
        return self._normalise(
            start_hand_for_testing(self._rules, session_id, players, deck, button_seat)
        )

    # -- actions -------------------------------------------------------------------

    def _decide(
        self, state: GameState, action: GameAction, payload: TexasPayload
    ) -> GameError | str:
        require_exact(state, GameState, "state")
        require_exact(action, GameAction, "action")
        require_exact(payload, TexasPayload, "payload")
        ext = state.extension
        if not isinstance(ext, TexasPublic):
            return GameError(WRONG_GAME, "This is not a Texas hold'em game")
        if state.public.status is not GameStatus.IN_PROGRESS or state.public.turn is None:
            return GameError(GAME_OVER, "The hand is over")
        if action.state_version != state.public.state_version:
            return GameError(STALE_STATE, "The game state is out of date")
        if action.player_id != state.public.turn.player_id:
            return GameError(NOT_YOUR_TURN, "It is not your turn")
        kind = action.type
        if kind not in KNOWN_ACTIONS:
            return GameError(UNKNOWN_ACTION, "Unknown action")
        if kind in UNSUPPORTED_ACTIONS:
            return GameError(NOT_SUPPORTED_YET, "Betting and raising are not supported yet")
        if payload.amount is not None:
            return GameError(BAD_PAYLOAD, "This action takes no amount")
        legal = legal_actions(state)
        if legal is None:
            return GameError(GAME_OVER, "The hand is over")
        if kind == ALL_IN and kind not in legal.kinds:
            # an all-in larger than the call amount is a raise (or a bet): P3-03
            return GameError(NOT_SUPPORTED_YET, "An all-in raise is not supported yet")
        if kind not in legal.kinds:
            return GameError(ILLEGAL_ACTION, "That action is not allowed now")
        return kind

    def validate_action(
        self, state: GameState, action: GameAction, payload: TexasPayload
    ) -> ActionValidation:
        decision = self._decide(state, action, payload)
        return ActionValidation(decision if isinstance(decision, GameError) else None)

    def apply_action(
        self, state: GameState, action: GameAction, payload: TexasPayload
    ) -> ApplyResult | GameError:
        decision = self._decide(state, action, payload)
        if isinstance(decision, GameError):
            return decision
        ext = state.extension
        seat = seat_to_act(state)
        if not isinstance(ext, TexasPublic) or seat is None:
            return GameError(GAME_OVER, "The hand is over")
        paid = 0
        if decision == FOLD:
            updated = replace(seat, folded=True)
        elif decision == CHECK:
            updated = replace(seat, acted=True)
        else:  # call, or an all-in that does not exceed the call amount
            paid = min(amount_to_call(ext, seat), seat.stack)
            stack = seat.stack - paid
            updated = replace(
                seat,
                stack=stack,
                committed=seat.committed + paid,
                street_committed=seat.street_committed + paid,
                acted=True,
                all_in=stack == 0,
            )
        seats = tuple(updated if s.seat == seat.seat else s for s in ext.seats)
        # The table data after the action; a lone survivor already marks the hand as ended.
        lone = sum(1 for s in seats if not s.folded) == 1
        after = replace(
            ext,
            seats=seats,
            pot=ext.pot + paid,
            ended=HandEnd.LAST_STANDING if lone else ext.ended,
        )
        base_seq = ext.event_seq
        new_state, payloads = advance(
            state,
            after,
            self._rules.burn_cards,
            seat.seat,
            [ActionTaken(seat.seat, decision, paid)],
        )
        events = tuple(
            GameEvent(base_seq + index, type(item).__name__, EventVisibility.PUBLIC, payload=item)
            for index, item in enumerate(payloads)
        )
        return ApplyResult(new_state, events)

    # -- views and results ---------------------------------------------------------

    def get_player_view(self, state: GameState, viewer_id: PlayerId) -> PlayerView | GameError:
        return project_player_view(state, viewer_id)

    def is_game_over(self, state: GameState) -> bool:
        return state.public.status is GameStatus.FINISHED

    def calculate_result(self, state: GameState) -> GameResult | GameError:
        if not self.is_game_over(state):
            return GameError(NOT_FINISHED, "The hand is not finished")
        return GameError(NOT_IMPLEMENTED, "Settlement is not implemented yet")
