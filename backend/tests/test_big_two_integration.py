"""Phase D integration tests for the Big Two private-room prototype.

They drive the real router over WebSockets (random production deck) and cover the D1 items
that the unit tests did not assert directly: state restoration after a mid-trick reconnect,
per-member JSON isolation, and exactly-once settlement of a finishing action over the wire.
"""

import json
import re
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from app.games.big_two.config import card_key
from app.games.core.card import Card
from app.prototype.big_two import build_big_two_router

ROOMS = "/api/proto/big-two/rooms"
CARD_CODE = re.compile(r'"((?:10|[2-9JQKA])[CDHS])"')
STATE_KEYS = ("turn", "target", "passes", "state_version", "counts", "played", "hand", "opening")

type View = dict[str, object]


class Table:
    """Four connected members of one room, with the latest view each of them received."""

    def __init__(self, client: TestClient, stack: ExitStack) -> None:
        self.client = client
        self.stack = stack
        created = client.post(ROOMS, json={"nickname": "A"}).json()
        self.path = f"{ROOMS}/{created['room']}"
        self.tokens = [created["token"]] + [
            client.post(f"{self.path}/join", json={"nickname": name}).json()["token"]
            for name in "BCD"
        ]
        self.sockets: list[WebSocketTestSession] = []
        for token in self.tokens:
            self.sockets.append(self.connect(token))
            for earlier in self.sockets:
                earlier.receive_json()
        self.views: list[View] = []
        self.last_request: dict[str, object] = {}

    def connect(self, token: str) -> WebSocketTestSession:
        socket = self.stack.enter_context(self.client.websocket_connect(f"{self.path}/ws"))
        socket.send_json({"token": token})
        return socket

    def start(self) -> None:
        self.sockets[0].send_json({"type": "start"})
        self.views = [socket.receive_json() for socket in self.sockets]

    def game(self, seat: int) -> dict[str, object]:
        game = self.views[seat]["game"]
        assert isinstance(game, dict)
        return game

    def hand(self, seat: int) -> list[str]:
        hand = self.game(seat)["hand"]
        assert isinstance(hand, list)
        return [str(code) for code in hand]

    def turn_seat(self) -> int:
        you = {str(view["you"]): seat for seat, view in enumerate(self.views)}
        return you[str(self.game(0)["turn"])]

    def message(self, seat: int, action: dict[str, object], request_id: str) -> dict[str, object]:
        game = self.game(seat)
        return {
            "type": "action",
            "game_id": game["game_id"],
            "request_id": request_id,
            "state_version": game["state_version"],
            "action": action,
        }

    def act(self, seat: int, action: dict[str, object]) -> dict[str, object]:
        """Send an accepted action; collect the receipt and every member's new view."""
        self.last_request = self.message(seat, action, str(uuid4()))
        self.sockets[seat].send_json(self.last_request)
        receipt: dict[str, object] = self.sockets[seat].receive_json()
        assert receipt["accepted"] is True, receipt
        self.views = [socket.receive_json() for socket in self.sockets]
        return receipt

    def reconnect(self, seat: int) -> View:
        """Replace one member's socket; every other member receives one broadcast view."""
        self.sockets[seat] = self.connect(self.tokens[seat])
        view: View = self.sockets[seat].receive_json()
        for other, socket in enumerate(self.sockets):
            if other != seat:
                self.views[other] = socket.receive_json()
        return view


@contextmanager
def table() -> Iterator[Table]:
    app = FastAPI()
    app.include_router(build_big_two_router())
    with TestClient(app) as client, ExitStack() as stack:
        yield Table(client, stack)


def assert_no_foreign_hand_cards(room: Table) -> None:
    """Each member's JSON may contain only their own hand and publicly played cards."""
    hands = [set(room.hand(seat)) for seat in range(4)]
    for seat, view in enumerate(room.views):
        game = room.game(seat)
        played_cards = game["played"]
        assert isinstance(played_cards, list)
        played = {str(code) for code in played_cards}
        found = set(CARD_CODE.findall(json.dumps(view)))
        foreign = set().union(*(hands[other] for other in range(4) if other != seat)) - played
        assert found <= hands[seat] | played, (seat, found - hands[seat] - played)
        assert not found & foreign, (seat, found & foreign)


def test_views_never_carry_another_members_unplayed_cards() -> None:
    with table() as room:
        room.start()
        assert_no_foreign_hand_cards(room)
        first = next(seat for seat in range(4) if "3C" in room.hand(seat))
        room.act(first, {"type": "play", "cards": ["3C"]})
        assert_no_foreign_hand_cards(room)
        room.act((first + 1) % 4, {"type": "pass"})
        assert_no_foreign_hand_cards(room)
        room.act((first + 2) % 4, {"type": "pass"})
        assert_no_foreign_hand_cards(room)


def test_mid_trick_reconnect_restores_turn_target_passes_and_hand() -> None:
    with table() as room:
        room.start()
        first = next(seat for seat in range(4) if "3C" in room.hand(seat))
        room.act(first, {"type": "play", "cards": ["3C"]})
        room.act((first + 1) % 4, {"type": "pass"})
        room.act((first + 2) % 4, {"type": "pass"})
        assert room.game(0)["passes"] == 2 and room.game(0)["target"] == ["3C"]
        for seat in ((first + 3) % 4, (first + 1) % 4, first):
            before = {key: room.game(seat)[key] for key in STATE_KEYS}
            restored = room.reconnect(seat)
            assert restored["you"] == room.views[seat]["you"]
            game = restored["game"]
            assert isinstance(game, dict)
            assert {key: game[key] for key in STATE_KEYS} == before
            room.views[seat] = restored
        assert room.game(0)["turn"] == room.views[(first + 3) % 4]["you"]
        assert_no_foreign_hand_cards(room)


def greedy_move(hand: list[str], target: list[str]) -> dict[str, object]:
    """Play singles only: lead the lowest card, beat a single with the lowest higher card."""
    if not target:
        return {"type": "play", "cards": [hand[0]]}
    bar = card_key(Card.from_code(target[0]))
    for code in hand:
        if card_key(Card.from_code(code)) > bar:
            return {"type": "play", "cards": [code]}
    return {"type": "pass"}


def points(room: Table, seat: int) -> list[int]:
    members = room.views[seat]["members"]
    assert isinstance(members, list)
    return [int(member["points"]) for member in members]


def test_finishing_action_settles_once_and_a_resend_changes_nothing() -> None:
    with table() as room:
        room.start()
        finisher = -1
        last_receipt: dict[str, object] = {}
        for _ in range(400):
            if room.game(0)["result"] is not None:
                break
            finisher = room.turn_seat()
            target = room.game(finisher)["target"]
            assert isinstance(target, list)
            last_receipt = room.act(finisher, greedy_move(room.hand(finisher), list(target)))
        else:
            raise AssertionError("the game did not finish")
        last_request = room.last_request

        result = room.game(0)["result"]
        assert isinstance(result, list) and len(result) == 4
        deltas = {str(entry["id"]): int(entry["delta"]) for entry in result}
        assert sum(deltas.values()) == 0
        assert [seat for seat in range(4) if not room.hand(seat)] == [finisher]
        settled = points(room, 0)
        assert settled == [deltas[str(view["you"])] for view in room.views]
        assert settled[finisher] == -sum(delta for delta in settled if delta < 0)

        # Resend of the finishing request: original receipt, no broadcast, no second credit.
        room.sockets[finisher].send_json(last_request)
        replay = room.sockets[finisher].receive_json()
        assert replay == {**last_receipt, "replayed": True}
        # A different request id after the game is over is refused, not applied again.
        room.sockets[finisher].send_json({**last_request, "request_id": str(uuid4())})
        assert room.sockets[finisher].receive_json()["code"] == "game_over"

        # The host starts the next game; cumulative points are kept and the game id is new.
        previous_game = room.game(0)["game_id"]
        room.sockets[0].send_json({"type": "start"})
        room.views = [socket.receive_json() for socket in room.sockets]
        assert room.game(0)["game_id"] != previous_game
        assert room.game(0)["result"] is None
        assert points(room, 0) == settled
        assert sorted(len(room.hand(seat)) for seat in range(4)) == [13] * 4
        assert_no_foreign_hand_cards(room)
