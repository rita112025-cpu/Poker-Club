from dataclasses import dataclass, replace
from uuid import UUID

from app.games.big_two.config import CONFIG, HAND_SIZE, OPENING_CARD, PLAYER_COUNT, card_key
from app.games.big_two.hands import classify
from app.games.core.card import Card
from app.games.core.deck import Deck
from app.games.core.engine import require_production_deck
from app.games.core.engine_types import (
    ActionValidation,
    ApplyResult,
    EventVisibility,
    GameConfig,
    GameEvent,
    GameResult,
    PlayerResult,
)
from app.games.core.extensions import PublicExtension, register_public_extension
from app.games.core.models import (
    GameAction,
    GameError,
    GameState,
    GameStatus,
    Player,
    PlayerView,
    PrivateGameData,
    PrivatePlayerData,
    PublicGameData,
    Turn,
)
from app.games.core.projection import project_player_view
from app.games.core.registry import EngineRegistration, EngineRegistry


@register_public_extension
@dataclass(frozen=True, slots=True)
class BigTwoPublic(PublicExtension):
    counts: tuple[int, ...]
    played: tuple[Card, ...] = ()
    target: tuple[Card, ...] = ()
    leader: UUID | None = None
    passes: int = 0

    def __post_init__(self) -> None:
        if (
            type(self.counts) is not tuple
            or len(self.counts) != PLAYER_COUNT
            or any(type(n) is not int or not 0 <= n <= HAND_SIZE for n in self.counts)
        ):
            raise ValueError("Invalid card counts")
        for cards in (self.played, self.target):
            if type(cards) is not tuple or any(type(card) is not Card for card in cards):
                raise TypeError("Expected public cards")
        if len(set(self.played)) != len(self.played) or sum(self.counts) + len(self.played) != 52:
            raise ValueError("Cards must be conserved")
        if self.target and (
            self.played[-len(self.target) :] != self.target or classify(self.target) is None
        ):
            raise ValueError("Invalid target")
        if self.leader is not None and type(self.leader) is not UUID:
            raise TypeError("Invalid leader")
        if type(self.passes) is not int or not 0 <= self.passes < PLAYER_COUNT - 1:
            raise ValueError("Invalid pass count")
        if (not self.target and self.passes) or (self.target and self.leader is None):
            raise ValueError("Inconsistent trick")

    def check_consistency(self, public: object) -> None:
        if not isinstance(public, PublicGameData) or len(public.players) != PLAYER_COUNT:
            raise ValueError("Big Two requires four seats")
        if self.leader is not None and self.leader not in {p.id for p in public.players}:
            raise ValueError("Leader must be a player")
        finished = public.status is GameStatus.FINISHED
        if finished != (self.counts.count(0) == 1) or finished != (public.turn is None):
            raise ValueError("Inconsistent finished state")


def score(players: tuple[Player, ...], counts: tuple[int, ...]) -> GameResult:
    if len(players) != PLAYER_COUNT or len(counts) != PLAYER_COUNT or counts.count(0) != 1:
        raise ValueError("Expected four players and exactly one winner")
    if any(type(count) is not int or not 0 <= count <= HAND_SIZE for count in counts):
        raise ValueError("Invalid remaining count")
    return GameResult(
        tuple(
            PlayerResult(p.id, -count if count else sum(counts), 1 + sum(n < count for n in counts))
            for p, count in zip(players, counts, strict=True)
        )
    )


class BigTwoEngine:
    def create_game(
        self, config: GameConfig, session_id: UUID, players: tuple[Player, ...], deck: Deck
    ) -> GameState | GameError:
        return self._deal(config, session_id, players, require_production_deck(deck))

    def _deal(
        self, config: GameConfig, session_id: UUID, players: tuple[Player, ...], deck: Deck
    ) -> GameState | GameError:
        if config != CONFIG:
            return GameError("rules_mismatch", "Unknown Big Two rules")
        if (
            len(players) != PLAYER_COUNT
            or len({p.id for p in players}) != PLAYER_COUNT
            or len({p.seat for p in players}) != PLAYER_COUNT
        ):
            return GameError("invalid_players", "Big Two requires four distinct players and seats")
        cards = deck.deal(52)
        seats = sorted(players, key=lambda player: player.seat)
        hands = tuple(
            PrivatePlayerData(player.id, tuple(sorted(cards[index::PLAYER_COUNT], key=card_key)))
            for index, player in enumerate(seats)
        )
        opener = next(hand.player_id for hand in hands if OPENING_CARD in hand.hand)
        return GameState(
            session_id,
            CONFIG.game_type,
            CONFIG.rules_version,
            PublicGameData(GameStatus.IN_PROGRESS, 0, players, Turn(opener)),
            PrivateGameData(hands),
            BigTwoPublic((HAND_SIZE,) * PLAYER_COUNT),
        )

    def _validate(
        self, state: GameState, action: GameAction, payload: tuple[str, ...]
    ) -> tuple[Card, ...] | GameError:
        def error(code: str, message: str) -> GameError:
            return GameError(code, message, action.request_id)

        table = state.extension
        if not isinstance(table, BigTwoPublic) or (state.game_type, state.rules_version) != (
            CONFIG.game_type,
            CONFIG.rules_version,
        ):
            return error("rules_mismatch", "Unknown Big Two rules")
        if self.is_game_over(state):
            return error("game_over", "本局已結束")
        if action.state_version != state.public.state_version:
            return error("stale_state", "畫面已過期")
        if state.public.turn != Turn(action.player_id):
            return error("not_your_turn", "還沒輪到你")
        if action.type == "pass":
            if payload or not table.target:
                return error("illegal_play", "目前不能過牌")
            return ()
        if action.type != "play":
            return error("illegal_play", "不支援此動作")
        try:
            cards = tuple(sorted(map(Card.from_code, payload), key=card_key))
        except (TypeError, ValueError):
            return error("invalid_cards", "選取的牌無法出牌")
        own = next(p.hand for p in state.private.players if p.player_id == action.player_id)
        if len(set(cards)) != len(cards) or not set(cards).issubset(own):
            return error("invalid_cards", "選取的牌無法出牌")
        hand = classify(cards)
        target = classify(table.target)
        if (
            hand is None
            or (not table.played and OPENING_CARD not in cards)
            or (target is not None and not hand.beats(target))
        ):
            return error("illegal_play", "這組牌目前不能打出")
        return cards

    def validate_action(
        self, state: GameState, action: GameAction, payload: tuple[str, ...]
    ) -> ActionValidation:
        result = self._validate(state, action, payload)
        return ActionValidation(result if isinstance(result, GameError) else None)

    def apply_action(
        self, state: GameState, action: GameAction, payload: tuple[str, ...]
    ) -> ApplyResult | GameError:
        cards = self._validate(state, action, payload)
        if isinstance(cards, GameError):
            return cards
        table = state.extension
        assert isinstance(table, BigTwoPublic)
        players = state.public.players
        order = [p.id for p in sorted(players, key=lambda player: player.seat)]
        actor = action.player_id
        next_actor = order[(order.index(actor) + 1) % PLAYER_COUNT]
        private = state.private
        if cards:
            hands = tuple(
                replace(hand, hand=tuple(card for card in hand.hand if card not in cards))
                if hand.player_id == actor
                else hand
                for hand in private.players
            )
            private = PrivateGameData(hands)
            counts = {hand.player_id: len(hand.hand) for hand in hands}
            table = BigTwoPublic(
                tuple(counts[p.id] for p in players), table.played + cards, cards, actor
            )
        elif table.passes == PLAYER_COUNT - 2:
            assert table.leader is not None
            next_actor = table.leader
            table = replace(table, target=(), passes=0)
        else:
            table = replace(table, passes=table.passes + 1)
        finished = 0 in table.counts
        version = state.public.state_version + 1
        public = replace(
            state.public,
            status=GameStatus.FINISHED if finished else GameStatus.IN_PROGRESS,
            turn=None if finished else Turn(next_actor),
            state_version=version,
        )
        event = GameEvent(version, f"big_two_{action.type}", EventVisibility.PUBLIC)
        return ApplyResult(
            replace(state, public=public, private=private, extension=table), (event,)
        )

    def get_player_view(self, state: GameState, viewer_id: UUID) -> PlayerView | GameError:
        return project_player_view(state, viewer_id)

    def is_game_over(self, state: GameState) -> bool:
        return state.public.status is GameStatus.FINISHED

    def calculate_result(self, state: GameState) -> GameResult | GameError:
        if not self.is_game_over(state) or not isinstance(state.extension, BigTwoPublic):
            return GameError("game_in_progress", "本局尚未結束")
        return score(state.public.players, state.extension.counts)


def register_big_two(registry: EngineRegistry) -> BigTwoEngine:
    engine = BigTwoEngine()
    problem = registry.register(
        EngineRegistration(
            CONFIG.game_type,
            CONFIG.rules_version,
            PLAYER_COUNT,
            PLAYER_COUNT,
            engine,
        )
    )
    if problem is not None:
        raise ValueError(problem.message)
    return engine
