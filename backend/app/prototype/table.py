"""One prototype table: members, button rotation, hand lifecycle and per-player views.

The engine decides everything about a hand; this module only drives it (create, apply,
settle once) and serialises what each player may see. Views are built from the public state
plus the viewer's own hole cards; they never read other players' private data, and the
settlement shown is the minimal option (A): payouts, stacks and the cards revealed at a
showdown. Pot-by-pot detail stays undecided policy (contract clause R9.7).
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from app.games.core import Deck, GameAction, GameConfig, GameError, GameState, GameStatus, Player
from app.games.texas_holdem import (
    TEXAS_CODE,
    LegalActions,
    TexasEngine,
    TexasPayload,
    TexasPublic,
    TexasRules,
    legal_actions,
)

MAX_MEMBERS = 9
MIN_PLAYERS = 2
NICKNAME_MAX = 16

HAND_IN_PROGRESS = "hand_in_progress"
TABLE_FULL = "table_full"
BAD_NICKNAME = "bad_nickname"
NAME_TAKEN = "name_taken"
NOT_HOST = "not_host"
NOT_ENOUGH_PLAYERS = "not_enough_players"
NO_HAND = "no_hand"


@dataclass(slots=True)
class Member:
    player_id: UUID
    nickname: str
    stack: int
    token: str = field(repr=False)
    connected: bool = False


@dataclass(slots=True)
class PrototypeTable:
    code: str
    engine: TexasEngine
    rules: TexasRules
    starting_points: int
    members: list[Member] = field(default_factory=list)
    host_id: UUID | None = None
    button_id: UUID | None = None
    hand_no: int = 0
    state: GameState | None = None
    # Nickname -> chips at the end of the last hand, for the "who won" line.
    last_summary: list[dict[str, Any]] = field(default_factory=list)

    # -- membership ------------------------------------------------------------------

    def hand_in_progress(self) -> bool:
        return self.state is not None and self.state.public.status is GameStatus.IN_PROGRESS

    def join(self, nickname: str, token: str) -> Member | GameError:
        name = nickname.strip() if isinstance(nickname, str) else ""
        if not 1 <= len(name) <= NICKNAME_MAX:
            return GameError(BAD_NICKNAME, f"Nickname must be 1 to {NICKNAME_MAX} characters")
        if self.hand_in_progress():
            return GameError(HAND_IN_PROGRESS, "A hand is in progress; join between hands")
        if len(self.members) >= MAX_MEMBERS:
            return GameError(TABLE_FULL, "The table is full")
        if any(m.nickname == name for m in self.members):
            return GameError(NAME_TAKEN, "That nickname is already used at this table")
        member = Member(uuid4(), name, self.starting_points, token)
        self.members.append(member)
        if self.host_id is None:
            self.host_id = member.player_id
        return member

    def member_for_token(self, token: str) -> Member | None:
        return next((m for m in self.members if m.token == token), None)

    def _member(self, player_id: UUID) -> Member | None:
        return next((m for m in self.members if m.player_id == player_id), None)

    # -- hand lifecycle --------------------------------------------------------------

    def _next_button(self, active: list[Member]) -> UUID:
        if self.button_id is None:
            return active[0].player_id
        names = [m.player_id for m in self.members]
        start = names.index(self.button_id) if self.button_id in names else -1
        live = {m.player_id for m in active}
        for step in range(1, len(self.members) + 1):
            candidate = names[(start + step) % len(names)]
            if candidate in live:
                return candidate
        return active[0].player_id

    def start_hand(self, requester: UUID) -> GameError | None:
        if requester != self.host_id:
            return GameError(NOT_HOST, "Only the host starts a hand")
        if self.hand_in_progress():
            return GameError(HAND_IN_PROGRESS, "A hand is in progress")
        active = [m for m in self.members if m.stack >= 1]
        if len(active) < MIN_PLAYERS:
            return GameError(NOT_ENOUGH_PLAYERS, "At least two players with chips are needed")
        button = self._next_button(active)
        # The engine puts the button on the lowest seat, so number the seats clockwise
        # starting at the button player; clockwise order is unchanged.
        first = next(i for i, m in enumerate(active) if m.player_id == button)
        ordered = active[first:] + active[:first]
        players = tuple(
            Player(m.player_id, m.nickname, seat, m.stack) for seat, m in enumerate(ordered)
        )
        created = self.engine.create_game(
            GameConfig(TEXAS_CODE, self.rules.version), uuid4(), players, Deck()
        )
        if isinstance(created, GameError):
            return created
        self.button_id = button
        self.hand_no += 1
        self.last_summary = []
        self.state = created
        self._settle_if_over()
        return None

    def _settle_if_over(self) -> None:
        state = self.state
        if state is None or not self.engine.is_game_over(state):
            return
        settled = self.engine.settle_hand(state)
        if isinstance(settled, GameError):
            return
        self.state = settled.state
        table = settled.state.extension
        if not isinstance(table, TexasPublic):
            return
        summary: list[dict[str, Any]] = []
        for seat in table.seats:
            member = self._member(seat.player_id)
            if member is None:
                continue
            member.stack = seat.stack
            summary.append(
                {
                    "nickname": member.nickname,
                    "net": seat.stack - self._start_points(settled.state, seat.player_id),
                    "stack": seat.stack,
                }
            )
        self.last_summary = summary

    @staticmethod
    def _start_points(state: GameState, player_id: UUID) -> int:
        return next(p.points for p in state.public.players if p.id == player_id)

    def act(
        self, player_id: UUID, kind: str, amount: int | None, state_version: int
    ) -> GameError | None:
        state = self.state
        if state is None:
            return GameError(NO_HAND, "There is no hand")
        action = GameAction(player_id, uuid4(), state_version, kind)
        result = self.engine.apply_action(state, action, TexasPayload(amount))
        if isinstance(result, GameError):
            return result
        self.state = result.state
        self._settle_if_over()
        return None

    # -- serialisation ---------------------------------------------------------------

    def view_for(self, viewer: UUID) -> dict[str, Any]:
        me = self._member(viewer)
        names = {m.player_id: m.nickname for m in self.members}
        return {
            "type": "view",
            "room": self.code,
            "you": str(viewer),
            "is_host": viewer == self.host_id,
            "hand_no": self.hand_no,
            "blinds": [self.rules.small_blind, self.rules.big_blind],
            "members": [
                {
                    "id": str(m.player_id),
                    "nickname": m.nickname,
                    "stack": m.stack,
                    "connected": m.connected,
                    "host": m.player_id == self.host_id,
                }
                for m in self.members
            ],
            "summary": self.last_summary,
            "game": None if self.state is None or me is None else self._game(viewer, names),
        }

    def _game(self, viewer: UUID, names: dict[UUID, str]) -> dict[str, Any] | None:
        state = self.state
        table = state.extension if state is not None else None
        if state is None or not isinstance(table, TexasPublic):
            return None
        own: list[str] = []
        if any(p.id == viewer for p in state.public.players):
            view = self.engine.get_player_view(state, viewer)
            if not isinstance(view, GameError):
                own = [card.code for card in view.private.hand]
        shown = {hand.seat: [c.code for c in hand.cards] for hand in table.showdown}
        turn = state.public.turn
        legal: LegalActions | None = (
            legal_actions(state) if turn is not None and turn.player_id == viewer else None
        )
        seats = []
        for seat in table.seats:
            cards: list[str] | None
            if seat.player_id == viewer:
                cards = own
            else:
                cards = shown.get(seat.seat)
            seats.append(
                {
                    "player_id": str(seat.player_id),
                    "nickname": names.get(seat.player_id, "?"),
                    "seat": seat.seat,
                    "stack": seat.stack,
                    "committed": seat.committed,
                    "street_committed": seat.street_committed,
                    "folded": seat.folded,
                    "all_in": seat.all_in,
                    "payout": seat.payout,
                    "button": seat.seat == table.button_seat,
                    "small_blind": seat.seat == table.small_blind_seat,
                    "big_blind": seat.seat == table.big_blind_seat,
                    "cards": cards,
                }
            )
        return {
            "state_version": state.public.state_version,
            "street": table.street.value,
            "board": [card.code for card in table.board],
            "pot": table.pot,
            "current_bet": table.current_bet,
            "over": state.public.status is GameStatus.FINISHED,
            "settled": table.settled,
            "ended": table.ended.value,
            "turn": None if turn is None else str(turn.player_id),
            "legal": None
            if legal is None
            else {
                "kinds": list(legal.kinds),
                "to_call": legal.to_call,
                "min_to": legal.min_to,
                "max_to": legal.max_to,
            },
            "seats": seats,
        }
