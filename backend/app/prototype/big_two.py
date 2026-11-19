"""Opt-in, in-memory Big Two rooms for private prototype use."""

import asyncio
import secrets
from collections import deque
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from time import monotonic
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.games.big_two.config import CONFIG, PLAYER_COUNT
from app.games.big_two.engine import BigTwoEngine, BigTwoPublic, register_big_two
from app.games.core.deck import Deck
from app.games.core.engine_types import GameResult
from app.games.core.models import GameAction, GameError, GameState, Player, PlayerView
from app.games.core.registry import EngineRegistry

IDLE_LIMIT = 30 * 60
RECEIPT_LIMIT = 256
ROOM_LIMIT = 50
SEND_TIMEOUT = 2


class JoinBody(BaseModel):
    nickname: str


@dataclass(slots=True)
class Member:
    player: Player
    token: str = field(repr=False)
    socket: WebSocket | None = None
    points: int = 0


type Reply = dict[str, object]
type Fingerprint = tuple[int, str, tuple[str, ...]]


@dataclass(slots=True)
class Room:
    code: str
    offline_since: float | None
    members: list[Member] = field(default_factory=list)
    state: GameState | None = None
    result: GameResult | None = None
    games: deque[UUID] = field(default_factory=lambda: deque(maxlen=2))
    receipts: dict[tuple[UUID, UUID], dict[UUID, tuple[Fingerprint, Reply]]] = field(
        default_factory=dict
    )
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    closed: bool = False

    def expired(self, now: float) -> bool:
        return self.offline_since is not None and now - self.offline_since >= IDLE_LIMIT

    def add(self, nickname: str) -> Reply:
        nickname = nickname.strip()
        if not 1 <= len(nickname) <= 16:
            raise HTTPException(422, detail="暱稱需為 1 到 16 個字")
        if len(self.members) >= PLAYER_COUNT:
            raise HTTPException(409, detail="房間已滿")
        if any(member.player.display_name == nickname for member in self.members):
            raise HTTPException(409, detail="暱稱已被使用")
        member = Member(Player(uuid4(), nickname, len(self.members)), secrets.token_urlsafe(24))
        self.members.append(member)
        return {"room": self.code, "token": member.token}

    def start(self, engine: BigTwoEngine, member: Member) -> str | None:
        if member is not self.members[0]:
            return "not_host"
        if self.state is not None and self.result is None:
            return "game_in_progress"
        if len(self.members) != PLAYER_COUNT or any(m.socket is None for m in self.members):
            return "four_players_required"
        state = engine.create_game(CONFIG, uuid4(), tuple(m.player for m in self.members), Deck())
        if isinstance(state, GameError):
            return state.code
        self.state, self.result = state, None
        self.games.append(state.session_id)
        self.receipts = {key: value for key, value in self.receipts.items() if key[0] in self.games}
        return None

    def action(self, engine: BigTwoEngine, member: Member, message: dict[str, object]) -> Reply:
        try:
            game_id, request_id, fingerprint = parse_action(message)
        except (ValueError, TypeError):
            return {"type": "error", "code": "bad_message"}
        version, action_type, cards = fingerprint
        cache_key = (game_id, member.player.id)
        existing = self.receipts.get(cache_key, {}).get(request_id)
        reply: Reply = {
            "type": "receipt",
            "game_id": str(game_id),
            "request_id": str(request_id),
            "state_version": version,
            "accepted": False,
        }
        if existing is not None:
            if fingerprint == existing[0]:
                return {**existing[1], "replayed": True}
            return {**reply, "code": "request_id_conflict"}
        state = self.state
        if state is None or state.session_id != game_id:
            return {**reply, "code": "game_mismatch"}

        reply["state_version"] = state.public.state_version
        outcome = engine.apply_action(
            state, GameAction(member.player.id, request_id, version, action_type), cards
        )
        if isinstance(outcome, GameError):
            reply.update(code=outcome.code, message=outcome.message)
        else:
            finished = (
                engine.calculate_result(outcome.state)
                if engine.is_game_over(outcome.state)
                else None
            )
            if isinstance(finished, GameResult):
                deltas = {p.player_id: p.points_delta for p in finished.players}
                for participant in self.members:
                    participant.points += deltas[participant.player.id]
                self.result = finished
            self.state = outcome.state
            reply.update(accepted=True, state_version=self.state.public.state_version)
        cache = self.receipts.setdefault(cache_key, {})
        cache[request_id] = (fingerprint, reply)
        if len(cache) > RECEIPT_LIMIT:
            del cache[next(iter(cache))]
        return reply

    def view(self, engine: BigTwoEngine, member: Member) -> Reply:
        view: Reply = {
            "type": "view",
            "room": self.code,
            "you": str(member.player.id),
            "is_host": member is self.members[0],
            "members": [
                {
                    "id": str(m.player.id),
                    "name": m.player.display_name,
                    "connected": m.socket is not None,
                    "points": m.points,
                }
                for m in self.members
            ],
            "game": None,
        }
        if self.state is None:
            return view
        state = self.state
        projection = engine.get_player_view(state, member.player.id)
        assert isinstance(projection, PlayerView)
        table = projection.extension
        assert isinstance(table, BigTwoPublic)
        turn = projection.public.turn
        view["game"] = {
            "game_id": str(state.session_id),
            "rules_version": state.rules_version,
            "state_version": projection.public.state_version,
            "turn": str(turn.player_id) if turn is not None else None,
            "target": [card.code for card in table.target],
            "played": [card.code for card in table.played],
            "passes": table.passes,
            "counts": dict(
                zip(
                    (str(p.id) for p in projection.public.players),
                    table.counts,
                    strict=True,
                )
            ),
            "hand": [card.code for card in projection.private.hand],
            "opening": not table.played,
            "result": None
            if self.result is None
            else [
                {"id": str(p.player_id), "delta": p.points_delta, "rank": p.rank}
                for p in self.result.players
            ],
        }
        return view


def parse_action(message: dict[str, object]) -> tuple[UUID, UUID, Fingerprint]:
    game, request, version, action = (
        message.get(key) for key in ("game_id", "request_id", "state_version", "action")
    )
    if (
        set(message) != {"type", "game_id", "request_id", "state_version", "action"}
        or not isinstance(game, str)
        or not isinstance(request, str)
        or not isinstance(version, int)
        or type(version) is not int
        or version < 0
        or not isinstance(action, dict)
    ):
        raise ValueError("Invalid action")
    kind = action.get("type")
    if kind == "pass" and set(action) == {"type"}:
        return UUID(game), UUID(request), (version, "pass", ())
    cards = action.get("cards")
    if (
        kind != "play"
        or set(action) != {"type", "cards"}
        or not isinstance(cards, list)
        or not all(isinstance(card, str) for card in cards)
    ):
        raise ValueError("Invalid action")
    return UUID(game), UUID(request), (version, "play", tuple(sorted(cards)))


def build_big_two_router(clock: Callable[[], float] = monotonic) -> APIRouter:
    rooms: dict[str, Room] = {}
    engine = register_big_two(EngineRegistry())

    def sweep() -> None:
        for room in tuple(rooms.values()):
            if room.expired(clock()) and not room.lock.locked():
                room.closed = True
                del rooms[room.code]

    @asynccontextmanager
    async def lifespan(_: object) -> AsyncIterator[None]:
        async def cleaner() -> None:
            while True:
                await asyncio.sleep(60)
                sweep()

        task = asyncio.create_task(cleaner())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    router = APIRouter(prefix="/api/proto/big-two", lifespan=lifespan)

    async def send(socket: WebSocket, reply: Reply) -> None:
        await asyncio.wait_for(socket.send_json(reply), SEND_TIMEOUT)

    async def broadcast(room: Room) -> None:
        for member in room.members:
            socket = member.socket
            if socket is not None:
                try:
                    await send(socket, room.view(engine, member))
                except (WebSocketDisconnect, RuntimeError, TimeoutError, OSError):
                    member.socket = None
                    with suppress(WebSocketDisconnect, RuntimeError, TimeoutError, OSError):
                        await asyncio.wait_for(socket.close(), SEND_TIMEOUT)
        if all(m.socket is None for m in room.members) and room.offline_since is None:
            room.offline_since = clock()

    @router.get("/status")
    async def status() -> dict[str, bool]:
        return {"available": True}

    @router.post("/rooms")
    async def create(body: JoinBody) -> Reply:
        sweep()
        if len(rooms) >= ROOM_LIMIT:
            raise HTTPException(429, detail="房間數已達上限")
        while True:
            code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(5))
            if code not in rooms:
                break
        room = Room(code, clock())
        joined = room.add(body.nickname)
        rooms[code] = room
        return joined

    @router.post("/rooms/{code}/join")
    async def join(code: str, body: JoinBody) -> Reply:
        sweep()
        room = rooms.get(code.upper())
        if room is None:
            raise HTTPException(404, detail="找不到房間")
        async with room.lock:
            if room.closed or room.expired(clock()):
                raise HTTPException(404, detail="找不到房間")
            joined = room.add(body.nickname)
            await broadcast(room)
            return joined

    @router.websocket("/rooms/{code}/ws")
    async def connect(socket: WebSocket, code: str) -> None:
        await socket.accept()
        sweep()
        room = rooms.get(code.upper())
        member = None
        try:
            first = await asyncio.wait_for(socket.receive_json(), 10)
            token = first.get("token") if isinstance(first, dict) else None
            if room is None or not isinstance(token, str):
                await socket.close(code=4401)
                return
            async with room.lock:
                if room.closed or room.expired(clock()):
                    await socket.close(code=4401)
                    return
                member = next(
                    (
                        m
                        for m in room.members
                        if secrets.compare_digest(m.token.encode(), token.encode())
                    ),
                    None,
                )
                if member is None:
                    await socket.close(code=4401)
                    return
                old, member.socket = member.socket, socket
                room.offline_since = None
                if old is not None:
                    with suppress(WebSocketDisconnect, RuntimeError, TimeoutError, OSError):
                        await asyncio.wait_for(old.close(code=4000), SEND_TIMEOUT)
                await broadcast(room)

            while True:
                message = await socket.receive_json()
                async with room.lock:
                    if room.closed or member.socket is not socket:
                        return
                    kind = message.get("type") if isinstance(message, dict) else None
                    if kind == "close_room" and member is room.members[0]:
                        room.closed = True
                        rooms.pop(room.code, None)
                        for participant in room.members:
                            if participant.socket is not None:
                                with suppress(
                                    WebSocketDisconnect, RuntimeError, TimeoutError, OSError
                                ):
                                    await asyncio.wait_for(participant.socket.close(code=4001), 2)
                        return
                    if kind == "start":
                        problem = room.start(engine, member)
                        if problem is None:
                            await broadcast(room)
                        else:
                            await send(socket, {"type": "error", "code": problem})
                    elif kind == "action" and isinstance(message, dict):
                        reply = room.action(engine, member, message)
                        try:
                            await send(socket, reply)
                        finally:
                            if reply.get("accepted") is True and not reply.get("replayed"):
                                await broadcast(room)
                    else:
                        await send(socket, {"type": "error", "code": "bad_message"})
        except ValueError:
            # A frame that cannot be decoded as JSON is closed without a receipt.
            with suppress(WebSocketDisconnect, RuntimeError, OSError):
                await socket.close(code=1007)
        except (WebSocketDisconnect, TimeoutError, RuntimeError, OSError):
            pass
        finally:
            if room is not None and member is not None:
                async with room.lock:
                    if not room.closed and member.socket is socket:
                        member.socket = None
                        await broadcast(room)

    return router
