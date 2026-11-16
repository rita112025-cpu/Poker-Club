"""TexasEngine (P3-02, P3-03): the six GameEngine methods for no-limit betting rounds.

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
    BET,
    CALL,
    CHECK,
    FOLD,
    KNOWN_ACTIONS,
    RAISE,
    advance,
    amount_to_call,
    legal_actions,
    round_is_complete,
    seat_to_act,
    stack_total,
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
BAD_AMOUNT = "bad_amount"
NOT_FINISHED = "not_finished"
NOT_IMPLEMENTED = "not_implemented"


@dataclass(frozen=True, slots=True)
class TexasPayload:
    """Action payload; amount (raise-to: the seat's total this round) is required for bet and
    raise and must be None for every other action."""

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
        """If no betting is possible at the start (everyone all-in, or the only seat that can
        act has nothing to answer), deal the board out now."""
        if isinstance(created, GameError):
            return created
        table = created.extension
        if not isinstance(table, TexasPublic):
            return created
        if created.public.turn is not None and not round_is_complete(table):
            return created
        return advance(created, table, self._rules.burn_cards, self._rules.big_blind, None, [])[0]

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
    ) -> GameError | tuple[str, int | None]:
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
        wants_amount = kind in (BET, RAISE)
        if wants_amount and payload.amount is None:
            return GameError(BAD_PAYLOAD, "This action needs an amount")
        if not wants_amount and payload.amount is not None:
            return GameError(BAD_PAYLOAD, "This action takes no amount")
        legal = legal_actions(state)
        if legal is None:
            return GameError(GAME_OVER, "The hand is over")
        if kind not in legal.kinds:
            return GameError(ILLEGAL_ACTION, "That action is not allowed now")
        if wants_amount:
            amount = payload.amount
            if (
                amount is None
                or legal.min_to is None
                or legal.max_to is None
                or not legal.min_to <= amount <= legal.max_to
            ):
                return GameError(BAD_AMOUNT, "The amount is outside the allowed range")
        return kind, payload.amount

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
        kind, amount = decision
        paid = 0
        current_bet = ext.current_bet
        min_raise = ext.min_raise
        owed = amount_to_call(ext, seat)
        total = stack_total(seat)
        if kind == FOLD:
            updated = replace(seat, folded=True)
        elif kind == CHECK:
            updated = replace(seat, acted=True, bet_seen=ext.current_bet)
        elif kind == CALL or (kind == ALL_IN and total <= ext.current_bet):
            paid = min(owed, seat.stack)  # a short call puts in everything it has
            stack = seat.stack - paid
            updated = replace(
                seat,
                stack=stack,
                committed=seat.committed + paid,
                street_committed=seat.street_committed + paid,
                acted=True,
                all_in=stack == 0,
                bet_seen=ext.current_bet,
            )
        else:  # bet, raise, or an all-in that exceeds the call amount
            target = amount if kind in (BET, RAISE) and amount is not None else total
            paid = target - seat.street_committed
            stack = seat.stack - paid
            increment = target - ext.current_bet
            if increment >= ext.min_raise:  # a full raise sets the new minimum increment
                min_raise = increment
            current_bet = target
            updated = replace(
                seat,
                stack=stack,
                committed=seat.committed + paid,
                street_committed=target,
                acted=True,
                all_in=stack == 0,
                bet_seen=target,
            )
        seats = tuple(updated if s.seat == seat.seat else s for s in ext.seats)
        # The table data after the action; a lone survivor already marks the hand as ended.
        lone = sum(1 for s in seats if not s.folded) == 1
        after = replace(
            ext,
            seats=seats,
            pot=ext.pot + paid,
            current_bet=current_bet,
            min_raise=min_raise,
            ended=HandEnd.LAST_STANDING if lone else ext.ended,
        )
        base_seq = ext.event_seq
        new_state, payloads = advance(
            state,
            after,
            self._rules.burn_cards,
            self._rules.big_blind,
            seat.seat,
            [ActionTaken(seat.seat, kind, paid, updated.street_committed)],
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
