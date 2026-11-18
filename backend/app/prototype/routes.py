"""PROTOTYPE HTTP and WebSocket endpoints for the in-memory table (see package docstring).

REST creates or joins a room and returns a random bearer token; the WebSocket's first message
must present it. Every state change is pushed to each connected member as that member's own
view. There is no persistence, rate limiting or Origin check: private, trusted use only.
"""

import asyncio
import secrets
from dataclasses import dataclass, field
from uuid import UUID

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.core.config import Settings
from app.games.core import GameError
from app.prototype.assembly import build_texas_engine
from app.prototype.table import Member, PrototypeTable

ROOM_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ROOM_CODE_LENGTH = 5
MAX_ROOMS = 50
AUTH_TIMEOUT_SECONDS = 10


class NicknameBody(BaseModel):
    nickname: str


@dataclass(slots=True)
class Hub:
    settings: Settings
    rooms: dict[str, PrototypeTable] = field(default_factory=dict)
    sockets: dict[str, dict[str, WebSocket]] = field(default_factory=dict)

    def new_code(self) -> str:
        while True:
            code = "".join(secrets.choice(ROOM_ALPHABET) for _ in range(ROOM_CODE_LENGTH))
            if code not in self.rooms:
                return code

    def create_room(self) -> PrototypeTable:
        engine, rules = build_texas_engine(self.settings)
        table = PrototypeTable(
            self.new_code(), engine, rules, self.settings.prototype_starting_points
        )
        self.rooms[table.code] = table
        self.sockets[table.code] = {}
        return table

    async def broadcast(self, table: PrototypeTable) -> None:
        for player_id, socket in list(self.sockets.get(table.code, {}).items()):
            try:
                await socket.send_json(table.view_for(UUID(player_id)))
            except (RuntimeError, WebSocketDisconnect):
                self.sockets[table.code].pop(player_id, None)


def _problem(error: GameError) -> dict[str, str]:
    return {"type": "error", "code": error.code, "message": error.message}


def _integer(value: object) -> int | None:
    return value if type(value) is int else None


def build_router(settings: Settings) -> APIRouter:
    hub = Hub(settings)
    router = APIRouter(prefix="/api/proto", tags=["prototype"])

    def joined(table: PrototypeTable, nickname: str) -> dict[str, str]:
        member = table.join(nickname, secrets.token_urlsafe(24))
        if isinstance(member, GameError):
            raise HTTPException(status_code=409, detail=_problem(member))
        return {"room": table.code, "player_id": str(member.player_id), "token": member.token}

    @router.get("/status")
    def prototype_status() -> dict[str, bool]:
        return {"available": True}

    @router.post("/rooms")
    def create_room(body: NicknameBody) -> dict[str, str]:
        if len(hub.rooms) >= MAX_ROOMS:
            raise HTTPException(status_code=429, detail="Too many rooms")
        table = hub.create_room()
        try:
            return joined(table, body.nickname)
        except HTTPException:
            hub.rooms.pop(table.code, None)
            hub.sockets.pop(table.code, None)
            raise

    @router.post("/rooms/{code}/join")
    async def join_room(code: str, body: NicknameBody) -> dict[str, str]:
        table = hub.rooms.get(code.upper())
        if table is None:
            raise HTTPException(status_code=404, detail="Room not found")
        result = joined(table, body.nickname)
        await hub.broadcast(table)
        return result

    @router.websocket("/rooms/{code}/ws")
    async def room_socket(websocket: WebSocket, code: str) -> None:
        await websocket.accept()
        table = hub.rooms.get(code.upper())
        member: Member | None = None
        try:
            first = await asyncio.wait_for(websocket.receive_json(), AUTH_TIMEOUT_SECONDS)
            token = first.get("token") if isinstance(first, dict) else None
            if table is not None and isinstance(token, str):
                member = table.member_for_token(token)
            if table is None or member is None:
                await websocket.close(code=4401)
                return
            key = str(member.player_id)
            old = hub.sockets[table.code].get(key)
            hub.sockets[table.code][key] = websocket
            member.connected = True
            if old is not None:
                await old.close(code=4000)
            await hub.broadcast(table)
            while True:
                message = await websocket.receive_json()
                if await handle(table, member, message, websocket):
                    await hub.broadcast(table)
        except (WebSocketDisconnect, TimeoutError, ValueError, RuntimeError):
            pass
        finally:
            if table is not None and member is not None:
                if hub.sockets[table.code].get(str(member.player_id)) is websocket:
                    hub.sockets[table.code].pop(str(member.player_id), None)
                    member.connected = False
                    await hub.broadcast(table)

    async def handle(
        table: PrototypeTable, member: Member, message: object, websocket: WebSocket
    ) -> bool:
        """Apply one client message; True when the table changed (so views must be pushed)."""
        if not isinstance(message, dict):
            return False
        kind = message.get("type")
        error: GameError | None = None
        if kind == "start":
            error = table.start_hand(member.player_id)
        elif kind == "action":
            action = message.get("action")
            version = _integer(message.get("state_version"))
            amount = message.get("amount")
            if (
                not isinstance(action, str)
                or version is None
                or (amount is not None and _integer(amount) is None)
            ):
                error = GameError("bad_message", "Malformed action")
            else:
                error = table.act(member.player_id, action, _integer(amount), version)
        else:
            error = GameError("unknown_message", "Unknown message type")
        if error is not None:
            await websocket.send_json(_problem(error))
        return error is None

    return router
