from dataclasses import replace
from uuid import UUID

import pytest
from engine_contract_suite import ContractScenario, check_engine_contract
from extension_matrix import MATRICES, FieldMatrix, check_field_matrix

from app.games.big_two.config import CONFIG, RANKS, SUITS, card_key
from app.games.big_two.engine import BigTwoEngine, BigTwoPublic, register_big_two, score
from app.games.big_two.hands import Category, classify
from app.games.core.card import Card
from app.games.core.deck import Deck
from app.games.core.engine import TestOnlyDeckError
from app.games.core.engine_types import ApplyResult, GameResult
from app.games.core.models import GameAction, GameError, GameState, Player
from app.games.core.registry import EngineRegistry


def cards(text: str) -> tuple[Card, ...]:
    return tuple(map(Card.from_code, text.split()))


def test_combinations_and_strength() -> None:
    samples = (
        "3C 4D 5H 6S 7D",
        "3H 4H 6H 8H QH",
        "9C 9D 9H JC JD",
        "KC KD KH KS 2D",
        "8S 9S 10S JS QS",
    )
    hands = [classify(cards(sample)) for sample in samples]
    for left, low in enumerate(hands):
        assert low is not None
        assert not low.beats(low)
        for high in hands[left + 1 :]:
            assert high is not None and high.beats(low) and not low.beats(high)
    assert len(set(cards(" ".join(samples)))) == 25


@pytest.mark.parametrize(
    ("high", "low"),
    [
        ("3D", "3C"),
        ("3H", "3D"),
        ("3S", "3H"),
        ("4C", "3S"),
        ("2C", "AS"),
        ("7C 7S", "7D 7H"),
        ("8C 8D", "7C 7S"),
        ("8C 8D 8H", "7D 7H 7S"),
        ("3D 4C 5S 6H 7S", "3S 4H 5D 6C 7H"),
        ("8C 9D 10H JS QC", "7C 8D 9H 10S JD"),
        ("AC QC 9C 6C 3C", "AS JS 10S 8S 4S"),
        ("AH QH 9H 6H 3H", "AD QD 9D 6D 3D"),
        ("8C 8D 8H 3C 3D", "7C 7D 7H AC AD"),
        ("8C 8D 8H 8S 3D", "7C 7D 7H 7S 2C"),
        ("3S 4S 5S 6S 7S", "3H 4H 5H 6H 7H"),
        ("2C 2D", "AH AS"),
        ("2C 2D 2H", "AD AH AS"),
    ],
)
def test_comparison(high: str, low: str) -> None:
    a, b = classify(cards(high)), classify(cards(low))
    assert a is not None and b is not None and a.beats(b) and not b.beats(a)
    assert classify(tuple(reversed(cards(high)))) == a


def test_straights_and_boundaries() -> None:
    for suits, category in (("CDHSC", Category.STRAIGHT), ("CCCCC", Category.STRAIGHT_FLUSH)):
        previous = None
        for lo in range(8):
            run = tuple(
                Card(rank, next(s for s in SUITS if s.value == suit))
                for rank, suit in zip(RANKS[lo : lo + 5], suits, strict=True)
            )
            hand = classify(run)
            assert hand is not None and hand.category == category
            assert previous is None or hand.beats(previous)
            previous = hand
    for value in ("AC 2D 3H 4S 5C", "2C 3D 4H 5S 6C", "JC QD KH AS 2C"):
        assert classify(cards(value)) is None
        flush = classify(cards(" ".join(code[:-1] + "S" for code in value.split())))
        assert flush is not None and flush.category == Category.FLUSH


@pytest.mark.parametrize(
    "sample",
    ["", "3C 4C", "3C 3D 4C", "3C 3D 3H 3S", "3C 3D 4C 4D 5C", "3C 3C", "3C 4C 5C 6C 7C 8C"],
)
def test_illegal_combinations(sample: str) -> None:
    assert classify(cards(sample)) is None


def players() -> tuple[Player, ...]:
    return tuple(Player(UUID(int=i + 1), f"Player {i + 1}", i) for i in range(4))


def test_deal_and_full_hand() -> None:
    engine = register_big_two(EngineRegistry())
    order = tuple(Card(rank, suit) for rank in RANKS for suit in SUITS)
    with pytest.raises(TestOnlyDeckError):
        engine.create_game(CONFIG, UUID(int=99), players(), Deck.for_testing(order))
    for shift in range(4):
        shifted = order[shift:] + order[:shift]
        dealt = engine._deal(CONFIG, UUID(int=99), players(), Deck.for_testing(shifted))
        assert isinstance(dealt, GameState)
        assert dealt.public.turn is not None
        assert dealt.public.turn.player_id == players()[(-shift) % 4].id
        assert [len(hand.hand) for hand in dealt.private.players] == [13] * 4
        assert set().union(*(set(hand.hand) for hand in dealt.private.players)) == set(order)
    initial = engine._deal(CONFIG, UUID(int=99), players(), Deck.for_testing(order))
    assert isinstance(initial, GameState)
    state: GameState = initial

    def play(seat: int, code: str = "") -> None:
        nonlocal state
        action = GameAction(
            players()[seat].id,
            UUID(int=100 + state.public.state_version),
            state.public.state_version,
            "play" if code else "pass",
        )
        outcome = engine.apply_action(state, action, (code,) if code else ())
        assert isinstance(outcome, ApplyResult), outcome
        assert outcome.state.public.state_version == state.public.state_version + 1
        state = outcome.state
        table = state.extension
        assert isinstance(table, BigTwoPublic)
        all_cards = [*table.played, *(c for hand in state.private.players for c in hand.hand)]
        assert len(all_cards) == 52 and set(all_cards) == set(order)

    bad = GameAction(players()[1].id, UUID(int=7), 0, "play")
    assert engine.validate_action(state, bad, ("11C",)).error == GameError(
        "not_your_turn", "還沒輪到你", bad.request_id
    )
    for rank in RANKS[:-1]:
        play(0, rank.value + "C")
        play(1, rank.value + "D")
        play(2, rank.value + "H" if rank in RANKS[:4] else "")
        play(3)
    play(0, "2C")
    result = engine.calculate_result(state)
    assert isinstance(result, GameResult)
    assert [entry.points_delta for entry in result.players] == [23, -1, -9, -13]
    assert [entry.rank for entry in score(players(), (0, 2, 2, 5)).players] == [1, 2, 2, 4]
    late = replace(bad, state_version=state.public.state_version)
    error = engine.validate_action(state, late, ()).error
    assert error is not None and error.code == "game_over"


def test_pass_reentry_and_reset() -> None:
    engine = BigTwoEngine()
    ranks = tuple(Card(rank, suit) for rank in RANKS for suit in SUITS)
    a, b, c, d = players()
    # Swap 4C and 4H, then 5C and 5D, for the scripted re-entry.
    swaps = {"4C": "4H", "4H": "4C", "5C": "5D", "5D": "5C"}
    deck = Deck.for_testing(Card.from_code(swaps.get(card.code, card.code)) for card in ranks)
    state = engine._deal(CONFIG, UUID(int=1), players(), deck)
    assert isinstance(state, GameState)
    for player, code in (
        (a, "3C"),
        (b, ""),
        (c, "4C"),
        (d, ""),
        (a, ""),
        (b, "5C"),
        (c, ""),
        (d, ""),
        (a, ""),
    ):
        version = state.public.state_version
        result = engine.apply_action(
            state,
            GameAction(player.id, UUID(int=version + 1), version, "play" if code else "pass"),
            (code,) if code else (),
        )
        assert isinstance(result, ApplyResult), result
        state = result.state
    assert state.public.turn is not None and state.public.turn.player_id == b.id
    assert isinstance(state.extension, BigTwoPublic) and not state.extension.target


def test_shared_engine_contract() -> None:
    engine = BigTwoEngine()

    def action(state: GameState, player: UUID, kind: str, version: int | None = None) -> GameAction:
        return GameAction(
            player,
            UUID(int=state.public.state_version + 1),
            state.public.state_version if version is None else version,
            kind,
        )

    def next_legal(state: GameState) -> tuple[GameAction, tuple[str, ...]] | None:
        turn, table = state.public.turn, state.extension
        assert isinstance(table, BigTwoPublic)
        if turn is None:
            return None
        hand = next(p.hand for p in state.private.players if p.player_id == turn.player_id)
        target = card_key(table.target[0]) if table.target else None
        selected = next((card for card in hand if target is None or card_key(card) > target), None)
        if not table.played:
            return action(state, turn.player_id, "play"), ("3C",)
        if selected is None:
            return action(state, turn.player_id, "pass"), ()
        return action(state, turn.player_id, "play"), (selected.code,)

    def revealed(state: GameState) -> frozenset[Card]:
        assert isinstance(state.extension, BigTwoPublic)
        return frozenset(state.extension.played)

    check_engine_contract(
        engine,
        ContractScenario(
            CONFIG,
            UUID(int=99),
            players(),
            next_legal,
            lambda state: (action(state, UUID(int=555), "pass"), ()),
            lambda state: (action(state, players()[0].id, "pass", 999), ()),
            lambda state: (action(state, players()[0].id, "pass"), ()),
            revealed=revealed,
            max_steps=208,
        ),
    )


MATRICES[BigTwoPublic] = FieldMatrix(
    lambda **overrides: BigTwoPublic(
        **{
            "counts": (12, 13, 13, 13),
            "played": cards("3C"),
            "target": cards("3C"),
            "leader": UUID(int=1),
            "passes": 0,
            **overrides,
        }
    ),
    {
        "counts": "tuple",
        "played": "tuple",
        "target": "tuple",
        "leader": "uuid",
        "passes": "nonneg_int",
    },
    {
        "counts": [(13, 13, 13, 13), (12, 13, 13, True)],
        "played": [("3C",)],
        "target": [cards("4C")],
        "passes": [3],
    },
)


def test_big_two_public_field_matrix() -> None:
    check_field_matrix(BigTwoPublic, MATRICES[BigTwoPublic])
