"""Prototype table (path B): in-memory play through the registered engine.

Rule values are the prototype settings (5/10, 1000 points, no burn), not approved policy.
"""

import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings
from app.prototype.routes import build_router

STARTING = 1000


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(build_router(Settings(prototype_enabled=True)))
    with TestClient(app) as test_client:
        yield test_client


def make_room(client: TestClient, names: tuple[str, ...]) -> tuple[str, list[dict[str, str]]]:
    created = client.post("/api/proto/rooms", json={"nickname": names[0]}).json()
    seats = [created]
    for name in names[1:]:
        seats.append(
            client.post(f"/api/proto/rooms/{created['room']}/join", json={"nickname": name}).json()
        )
    return created["room"], seats


def connect_all(
    client: TestClient, room: str, seats: list[dict[str, str]], stack: Any
) -> list[WebSocketTestSession]:
    sockets = [
        stack.enter_context(client.websocket_connect(f"/api/proto/rooms/{room}/ws")) for _ in seats
    ]
    for index, (socket, seat) in enumerate(zip(sockets, seats, strict=True)):
        socket.send_json({"token": seat["token"]})
        # Connecting socket i pushes a view to sockets 0..i; read them all so every queue
        # is empty before the test sends its first command.
        for earlier in sockets[: index + 1]:
            earlier.receive_json()
    return sockets


def broadcast(sockets: list[WebSocketTestSession]) -> list[dict[str, Any]]:
    views: list[dict[str, Any]] = [socket.receive_json() for socket in sockets]
    assert all(view["type"] == "view" for view in views), views
    return views


def test_rooms_have_unique_nicknames_and_a_host(client: TestClient) -> None:
    room, seats = make_room(client, ("Ann", "Bob"))
    again = client.post(f"/api/proto/rooms/{room}/join", json={"nickname": "Ann"})
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "name_taken"
    assert client.post("/api/proto/rooms/NOPE1/join", json={"nickname": "Cy"}).status_code == 404
    assert client.post("/api/proto/rooms", json={"nickname": "  "}).status_code == 409
    assert len({seat["token"] for seat in seats}) == 2


def test_a_bad_token_is_refused(client: TestClient) -> None:
    room, _ = make_room(client, ("Ann", "Bob"))
    with client.websocket_connect(f"/api/proto/rooms/{room}/ws") as ws:
        ws.send_json({"token": "wrong"})
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 4401


def test_only_the_host_starts_a_hand(client: TestClient) -> None:
    from contextlib import ExitStack

    room, seats = make_room(client, ("Ann", "Bob"))
    with ExitStack() as stack:
        host, guest = connect_all(client, room, seats, stack)
        guest.send_json({"type": "start"})
        assert guest.receive_json()["code"] == "not_host"
        host.send_json({"type": "start"})
        views = broadcast([host, guest])
        assert views[0]["game"]["street"] == "pre_flop"


def play_to_the_end(
    sockets: list[WebSocketTestSession], views: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Everybody checks or calls until the hand is over (a real showdown path)."""
    for _ in range(60):
        game = views[0]["game"]
        if game["over"]:
            return views
        index = next(i for i, view in enumerate(views) if view["you"] == game["turn"])
        legal = views[index]["game"]["legal"]
        kind = "check" if "check" in legal["kinds"] else "call"
        sockets[index].send_json(
            {"type": "action", "action": kind, "state_version": game["state_version"]}
        )
        views = broadcast(sockets)
    raise AssertionError("the hand did not finish")


def test_full_hands_hide_cards_conserve_chips_and_rotate_the_button(client: TestClient) -> None:
    from contextlib import ExitStack

    room, seats = make_room(client, ("Ann", "Bob", "Cy"))
    with ExitStack() as stack:
        sockets = connect_all(client, room, seats, stack)
        sockets[0].send_json({"type": "start"})
        views = broadcast(sockets)
        buttons: list[str] = []
        for hand in range(3):
            game = views[0]["game"]
            for view in views:
                for seat in view["game"]["seats"]:
                    if seat["player_id"] == view["you"]:
                        assert len(seat["cards"]) == 2
                    else:
                        assert seat["cards"] is None  # never another player's hole cards
                raw = json.dumps(view)
                assert "remaining" not in raw
            buttons.append(next(s["nickname"] for s in game["seats"] if s["button"]))
            views = play_to_the_end(sockets, views)
            final = views[0]["game"]
            assert final["settled"] and final["over"]
            assert sum(member["stack"] for member in views[0]["members"]) == 3 * STARTING
            assert sum(seat["payout"] for seat in final["seats"]) == final["pot"]
            if hand < 2:
                sockets[0].send_json({"type": "start"})
                views = broadcast(sockets)
        assert len(set(buttons)) == 3  # the button visited every player


def test_joining_mid_hand_is_refused(client: TestClient) -> None:
    from contextlib import ExitStack

    room, seats = make_room(client, ("Ann", "Bob"))
    with ExitStack() as stack:
        sockets = connect_all(client, room, seats, stack)
        sockets[0].send_json({"type": "start"})
        broadcast(sockets)
        late = client.post(f"/api/proto/rooms/{room}/join", json={"nickname": "Cy"})
        assert late.status_code == 409
        assert late.json()["detail"]["code"] == "hand_in_progress"


def test_malformed_and_out_of_turn_messages_are_errors_not_crashes(client: TestClient) -> None:
    from contextlib import ExitStack

    room, seats = make_room(client, ("Ann", "Bob"))
    with ExitStack() as stack:
        sockets = connect_all(client, room, seats, stack)
        sockets[0].send_json({"type": "start"})
        views = broadcast(sockets)
        game = views[0]["game"]
        waiting = next(i for i, view in enumerate(views) if view["you"] != game["turn"])
        other = sockets[waiting]
        version = game["state_version"]
        other.send_json({"type": "action", "action": "call", "state_version": version})
        assert other.receive_json()["code"] == "not_your_turn"
        other.send_json({"type": "action", "action": 5, "state_version": "x"})
        assert other.receive_json()["code"] == "bad_message"
        other.send_json({"type": "action", "action": "raise", "amount": True, "state_version": 0})
        assert other.receive_json()["code"] == "bad_message"
        other.send_json({"type": "nonsense"})
        assert other.receive_json()["code"] == "unknown_message"
