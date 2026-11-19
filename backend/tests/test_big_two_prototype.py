from contextlib import ExitStack
from dataclasses import replace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.games.big_two.config import CONFIG, RANKS, SUITS
from app.games.big_two.engine import BigTwoEngine, BigTwoPublic
from app.games.core.card import Card
from app.games.core.deck import Deck
from app.games.core.models import GameState, PrivateGameData, PrivatePlayerData, Turn
from app.prototype.big_two import Room, build_big_two_router


def test_four_player_views_and_receipts() -> None:
    app = FastAPI()
    app.include_router(build_big_two_router())
    with TestClient(app) as client, ExitStack() as stack:
        path = "/api/proto/big-two/rooms"
        created = client.post(path, json={"nickname": "A"}).json()
        room = f"{path}/{created['room']}"
        members = [created] + [
            client.post(f"{room}/join", json={"nickname": name}).json() for name in "BCD"
        ]
        assert client.post(f"{room}/join", json={"nickname": "E"}).status_code == 409
        sockets = []
        for member in members:
            ws = stack.enter_context(client.websocket_connect(f"{room}/ws"))
            sockets.append(ws)
            ws.send_json({"token": member["token"]})
            for connected in sockets:
                assert connected.receive_json()["game"] is None
            if len(sockets) == 3:
                sockets[0].send_json({"type": "start"})
                assert sockets[0].receive_json()["code"] == "four_players_required"
        sockets[0].send_json({"type": "start"})
        views = [ws.receive_json() for ws in sockets]
        hands = [set(view["game"]["hand"]) for view in views]
        assert all(len(hand) == 13 for hand in hands)
        assert len(set.union(*hands)) == 52
        actor = next(i for i, hand in enumerate(hands) if "3C" in hand)
        state = views[actor]["game"]
        request = {
            "type": "action",
            "game_id": state["game_id"],
            "request_id": str(uuid4()),
            "state_version": 0,
            "action": {"type": "play", "cards": ["11C"]},
        }
        sockets[actor].send_json(request)
        rejected = sockets[actor].receive_json()
        assert rejected["code"] == "invalid_cards"
        sockets[actor].send_json(request)
        assert sockets[actor].receive_json() == {**rejected, "replayed": True}
        sockets[actor].send_json({**request, "state_version": 1})
        assert sockets[actor].receive_json()["code"] == "request_id_conflict"
        for selection, expected in (
            (["3c"], "invalid_cards"),
            (["3C", "3C"], "invalid_cards"),
            ([next(iter(hands[(actor + 1) % 4]))], "invalid_cards"),
            ([], "illegal_play"),
            ([3], "bad_message"),
        ):
            sockets[actor].send_json(
                {
                    **request,
                    "request_id": str(uuid4()),
                    "action": {"type": "play", "cards": selection},
                }
            )
            error = sockets[actor].receive_json()
            assert error["code"] == expected
            if expected == "invalid_cards":
                assert error["message"] == rejected["message"]
        request = {
            **request,
            "request_id": str(uuid4()),
            "action": {"type": "play", "cards": ["3C"]},
        }
        sockets[actor].send_json(request)
        sockets[actor].send_json(request)
        accepted = sockets[actor].receive_json()
        assert accepted["accepted"] and accepted["state_version"] == 1
        for ws in sockets:
            assert ws.receive_json()["game"]["target"] == ["3C"]
        assert sockets[actor].receive_json() == {**accepted, "replayed": True}
        sockets[actor].send_json({**request, "request_id": str(uuid4()), "game_id": str(uuid4())})
        assert sockets[actor].receive_json()["code"] == "game_mismatch"

        replacement = stack.enter_context(client.websocket_connect(f"{room}/ws"))
        replacement.send_json({"token": members[actor]["token"]})
        with pytest.raises(WebSocketDisconnect) as displaced:
            sockets[actor].receive_json()
        assert displaced.value.code == 4000
        assert "3C" not in replacement.receive_json()["game"]["hand"]
        replacement.send_text("not JSON")
        with pytest.raises(WebSocketDisconnect) as malformed:
            replacement.receive_json()
        assert malformed.value.code == 1007


@pytest.mark.parametrize(("elapsed", "accepted"), [(1799.999, True), (1800, False), (1801, False)])
def test_offline_expiry_boundary(elapsed: float, accepted: bool) -> None:
    now = 0.0

    def clock() -> float:
        return now

    app = FastAPI()
    app.include_router(build_big_two_router(clock))
    with TestClient(app) as client:
        body = client.post("/api/proto/big-two/rooms", json={"nickname": "A"}).json()
        now = elapsed
        with client.websocket_connect(f"/api/proto/big-two/rooms/{body['room']}/ws") as ws:
            ws.send_json({"token": body["token"]})
            if accepted:
                assert ws.receive_json()["type"] == "view"
            else:
                with pytest.raises(WebSocketDisconnect) as closed:
                    ws.receive_json()
                assert closed.value.code == 4401


def test_finished_receipt_and_fifo() -> None:
    engine = BigTwoEngine()
    room = Room("ABCDE", 0)
    for name in "ABCD":
        room.add(name)
    a, b, *_ = room.members
    order = tuple(Card(rank, suit) for rank in RANKS for suit in SUITS)
    game = engine._deal(
        CONFIG, uuid4(), tuple(m.player for m in room.members), Deck.for_testing(order)
    )
    assert isinstance(game, GameState)
    cards = (
        (Card.from_code("2C"), Card.from_code("2S")),
        (Card.from_code("2D"),),
        tuple(Card(rank, SUITS[2]) for rank in RANKS[4:]),
        tuple(Card(rank, SUITS[3]) for rank in RANKS if rank.value != "2")
        + (Card.from_code("AC"),),
    )
    played = tuple(card for card in order if not any(card in hand for hand in cards))
    before_finish = replace(
        game,
        public=replace(game.public, turn=Turn(a.player.id)),
        private=PrivateGameData(
            tuple(
                PrivatePlayerData(member.player.id, hand)
                for member, hand in zip(room.members, cards, strict=True)
            )
        ),
        extension=BigTwoPublic((2, 1, 9, 13), played),
    )
    room.state = before_finish
    room.games.append(game.session_id)
    request = {
        "type": "action",
        "game_id": str(game.session_id),
        "request_id": str(UUID(int=1)),
        "state_version": 0,
        "action": {"type": "play", "cards": ["2S", "2C"]},
    }
    reply = room.action(engine, a, request)
    assert reply["accepted"] is True
    assert [m.points for m in room.members] == [23, -1, -9, -13]
    reordered = {**request, "action": {"type": "play", "cards": ["2C", "2S"]}}
    assert room.action(engine, a, reordered) == {**reply, "replayed": True}
    other = {**request, "request_id": str(UUID(int=1000))}
    assert room.action(engine, b, other)["code"] == "game_over"
    for index in range(2, 257):
        assert (
            room.action(engine, a, {**request, "request_id": str(UUID(int=index))})["code"]
            == "game_over"
        )
    assert room.action(engine, a, request).get("replayed") is True
    room.action(engine, a, {**request, "request_id": str(UUID(int=257))})
    assert UUID(int=1) not in room.receipts[game.session_id, a.player.id]
    assert room.action(engine, b, other).get("replayed") is True
    assert room.action(engine, a, request)["code"] == "game_over"
    for member in room.members:
        member.socket = MagicMock(spec=WebSocket)
    assert room.start(engine, a) is None
    assert room.state.session_id != game.session_id
    assert room.action(engine, b, other).get("replayed") is True
    assert room.action(engine, b, {**other, "request_id": str(uuid4())})["code"] == "game_mismatch"
    assert [m.points for m in room.members] == [23, -1, -9, -13]

    new_game_id = room.state.session_id
    room.state = replace(before_finish, session_id=new_game_id)
    assert room.action(engine, a, {**request, "game_id": str(new_game_id)})["accepted"] is True
    assert [m.points for m in room.members] == [46, -2, -18, -26]


def test_online_guest_prevents_recovery_timer_and_owner_can_close() -> None:
    now = 0.0

    def clock() -> float:
        return now

    app = FastAPI()
    app.include_router(build_big_two_router(clock))
    with TestClient(app) as client:
        path = "/api/proto/big-two/rooms"
        host = client.post(path, json={"nickname": "A"}).json()
        room = f"{path}/{host['room']}"
        guest = client.post(f"{room}/join", json={"nickname": "B"}).json()
        with client.websocket_connect(f"{room}/ws") as guest_ws:
            guest_ws.send_json({"token": guest["token"]})
            assert guest_ws.receive_json()["type"] == "view"
            now = 1800
            with client.websocket_connect(f"{room}/ws") as host_ws:
                host_ws.send_json({"token": host["token"]})
                assert host_ws.receive_json()["is_host"] is True
                assert guest_ws.receive_json()["type"] == "view"
                host_ws.send_json({"type": "close_room"})
                for ws in (host_ws, guest_ws):
                    with pytest.raises(WebSocketDisconnect) as closed:
                        ws.receive_json()
                    assert closed.value.code == 4001
        assert client.post(f"{room}/join", json={"nickname": "C"}).status_code == 404
