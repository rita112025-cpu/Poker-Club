"""P3-01: Texas positions, rules, public table data and hand setup (no betting yet).

Expected positions are written out by hand, not derived with the code under test.
Rules values below are TEST FIXTURES, not product settings. Not applicable: actions,
streets after the flop deal, side pots, settlement, the engine (P3-02 onwards).
"""

import ast
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from engine_contract_suite import reveals_card
from extension_matrix import MATRICES, FieldMatrix, check_field_matrix

from app.games.core import (
    Card,
    Deck,
    GameError,
    GameState,
    GameStatus,
    Player,
    PlayerView,
    TestOnlyDeckError,
    project_player_view,
    require_production_deck,
)
from app.games.core.deck import DeckUnavailableError
from app.games.core.extensions import registered_public_extensions
from app.games.texas_holdem import (
    Positions,
    SeatState,
    Street,
    TexasPublic,
    TexasRules,
    initial_button,
    next_button,
    next_seat,
    positions,
    start_hand,
)
from app.games.texas_holdem.hand import start_hand_for_testing

RULES = TexasRules("test-1", 5, 10, False)  # fixture values only
SESSION = UUID(int=500)


def pid(number: int) -> UUID:
    return UUID(int=number)


def table(seats: tuple[int, ...], stack: int = 100) -> tuple[Player, ...]:
    return tuple(Player(pid(10 + seat), f"P{seat}", seat, stack) for seat in seats)


def fixed_deck() -> Deck:
    """The whole deck in a known order: AS KS QS ... then hearts etc., 52 distinct cards."""
    codes = [
        rank + suit
        for suit in "SHDC"
        for rank in ("A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2")
    ]
    return Deck.for_testing(Card.from_code(code) for code in codes)


# ---- rules -----------------------------------------------------------------------


def test_rules_validate_every_field() -> None:
    assert TexasRules("v", 1, 1, True).big_blind == 1
    for args, error in [
        (("", 5, 10, False), ValueError),
        ((" ", 5, 10, False), ValueError),
        ((b"v", 5, 10, False), TypeError),
        (("v", 0, 10, False), ValueError),
        (("v", 5, 4, False), ValueError),
        (("v", True, 10, False), TypeError),
        (("v", 5, 10.0, False), TypeError),
        (("v", 5, 10, 1), TypeError),
        (("v", 5, 10, None), TypeError),
    ]:
        with pytest.raises(error):
            TexasRules(*args)  # type: ignore[arg-type]


# ---- positions (hand-written expectations) ----------------------------------------

POSITION_TABLE: list[tuple[tuple[int, ...], int, Positions]] = [
    # heads-up: button is the small blind and acts first
    ((0, 1), 0, Positions(0, 0, 1, 0)),
    ((0, 1), 1, Positions(1, 1, 0, 1)),
    ((2, 6), 2, Positions(2, 2, 6, 2)),
    ((2, 6), 6, Positions(6, 6, 2, 6)),
    # three players
    ((0, 1, 2), 0, Positions(0, 1, 2, 0)),
    ((0, 1, 2), 1, Positions(1, 2, 0, 1)),
    ((0, 1, 2), 2, Positions(2, 0, 1, 2)),
    # four players
    ((0, 1, 2, 3), 0, Positions(0, 1, 2, 3)),
    ((0, 1, 2, 3), 3, Positions(3, 0, 1, 2)),
    # gapped seat numbers, wrapping
    ((1, 3, 4, 7, 9), 4, Positions(4, 7, 9, 1)),
    ((1, 3, 4, 7, 9), 7, Positions(7, 9, 1, 3)),
    ((1, 3, 4, 7, 9), 9, Positions(9, 1, 3, 4)),
    ((1, 3, 4, 7, 9), 1, Positions(1, 3, 4, 7)),
    # nine players
    (tuple(range(9)), 0, Positions(0, 1, 2, 3)),
    (tuple(range(9)), 7, Positions(7, 8, 0, 1)),
    (tuple(range(9)), 8, Positions(8, 0, 1, 2)),
]


@pytest.mark.parametrize("seats,button,expected", POSITION_TABLE)
def test_positions_match_the_hand_written_table(
    seats: tuple[int, ...], button: int, expected: Positions
) -> None:
    assert positions(seats, button) == expected
    assert positions(tuple(reversed(seats)), button) == expected  # input order is irrelevant


def test_rotation_visits_every_seat_in_a_cycle_for_every_table_size() -> None:
    for count in range(2, 10):
        seats = tuple(range(0, count * 2, 2))  # gapped
        button = initial_button(seats)
        assert button == seats[0]
        visited = []
        for _ in range(count):
            visited.append(button)
            button = next_button(seats, button)
        assert visited == list(seats) and button == seats[0]


def test_position_invariants_for_every_size_and_button() -> None:
    for count in range(2, 10):
        seats = tuple(range(count))
        for button in seats:
            spot = positions(seats, button)
            assert {spot.button, spot.small_blind, spot.big_blind} <= set(seats)
            assert spot.small_blind != spot.big_blind
            assert spot.big_blind == next_seat(seats, spot.small_blind)
            if count == 2:
                assert spot.small_blind == button and spot.first_to_act == button
            else:
                assert spot.small_blind == next_seat(seats, button)
                assert spot.first_to_act == next_seat(seats, spot.big_blind)


@pytest.mark.parametrize(
    "seats",
    [(), (1,), tuple(range(10)), (1, 1), (0, -1), [0, 1], (0, True), (0, "1"), None],
)
def test_invalid_seat_sets_are_rejected(seats: Any) -> None:
    with pytest.raises((TypeError, ValueError)):
        positions(seats, 0)


def test_button_and_seat_arguments_must_be_ints_in_the_seat_set() -> None:
    for bad in (5, -1, True, "0", None):
        with pytest.raises(ValueError):
            positions((0, 1, 2), cast(int, bad))
    with pytest.raises(ValueError):
        next_seat((0, 1, 2), 9)


# ---- public table data (extension) ---------------------------------------------------


def seat_state(**overrides: Any) -> SeatState:
    fields: dict[str, Any] = {
        "seat": 0,
        "player_id": pid(1),
        "stack": 90,
        "committed": 10,
        "all_in": False,
        "folded": False,
    }
    fields.update(overrides)
    return SeatState(**fields)


def texas_public(**overrides: Any) -> TexasPublic:
    fields: dict[str, Any] = {
        "street": Street.PRE_FLOP,
        "button_seat": 0,
        "small_blind_seat": 1,
        "big_blind_seat": 2,
        "seats": (
            seat_state(seat=0, player_id=pid(1), stack=100, committed=0),
            seat_state(seat=1, player_id=pid(2), stack=95, committed=5),
            seat_state(seat=2, player_id=pid(3), stack=90, committed=10),
        ),
        "board": (),
        "pot": 15,
        "current_bet": 10,
    }
    fields.update(overrides)
    return TexasPublic(**fields)


MATRICES[SeatState] = FieldMatrix(
    seat_state,
    {
        "seat": "nonneg_int",
        "player_id": "uuid",
        "stack": "nonneg_int",
        "committed": "nonneg_int",
        "all_in": "bool",
        "folded": "bool",
    },
    {"all_in": [True]},  # all-in while chips remain
)
MATRICES[TexasPublic] = FieldMatrix(
    texas_public,
    {
        "street": "enum",
        "button_seat": "nonneg_int",
        "small_blind_seat": "nonneg_int",
        "big_blind_seat": "nonneg_int",
        "seats": "tuple",
        "board": "tuple",
        "pot": "nonneg_int",
        "current_bet": "nonneg_int",
    },
    {
        "street": [SeatState],
        "seats": [(seat_state(),) * 2, (), (cast(Any, "seat"),) * 2],
        "board": [(Card.from_code("AS"), Card.from_code("AS")), (cast(Any, "AS"),)],
        "button_seat": [99],
        "small_blind_seat": [99, 2],
        "pot": [14],
    },
)


@pytest.mark.parametrize("cls", [SeatState, TexasPublic])
def test_texas_field_matrices_reject_every_attack(cls: type) -> None:
    check_field_matrix(cls, MATRICES[cls])


def test_every_registered_extension_under_app_has_a_field_matrix() -> None:
    app_extensions = {c for c in registered_public_extensions() if c.__module__.startswith("app.")}
    assert TexasPublic in app_extensions
    assert not [c.__name__ for c in app_extensions if c not in MATRICES], "add a field matrix"


def test_extension_invariants_beyond_field_types() -> None:
    texas_public()
    ok_seats = texas_public().seats
    with pytest.raises(ValueError, match="increasing"):
        texas_public(seats=(ok_seats[1], ok_seats[0], ok_seats[2]))
    with pytest.raises(ValueError, match="two seats"):
        texas_public(seats=(ok_seats[0], replace(ok_seats[1], player_id=pid(1)), ok_seats[2]))
    with pytest.raises(ValueError, match="needs 2 to 9"):
        texas_public(
            seats=(ok_seats[0],), pot=0, button_seat=0, small_blind_seat=0, big_blind_seat=0
        )
    with pytest.raises(ValueError, match="before the flop"):
        texas_public(board=(Card.from_code("AS"),))
    texas_public(street=Street.FLOP, board=tuple(Card.from_code(c) for c in ("AS", "KS", "QS")))
    with pytest.raises(ValueError, match="heads-up"):
        seats = (ok_seats[0], replace(ok_seats[1], committed=0))
        texas_public(seats=seats, pot=0, button_seat=0, small_blind_seat=1, big_blind_seat=0)
    with pytest.raises(ValueError):
        seat_state(all_in=True, stack=5)
    with pytest.raises(ValueError):
        seat_state(all_in=True, stack=0, folded=True)


def test_extension_subclass_smuggling_is_rejected_by_the_game_state() -> None:
    @dataclass(frozen=True, slots=True)
    class TexasWithHand(TexasPublic):
        hand: tuple[Card, ...] = ()

    base = texas_public()
    extra = cast(Any, TexasWithHand)(
        *(getattr(base, f) for f in base.__dataclass_fields__), hand=(Card.from_code("AS"),)
    )
    assert "hand" in asdict(extra)
    game = start_hand_for_testing(RULES, SESSION, table((0, 1, 2)), fixed_deck())
    assert isinstance(game, GameState)
    with pytest.raises(TypeError, match="exact registered public extension"):
        replace(game, extension=extra)


# ---- starting a hand ---------------------------------------------------------------------


@pytest.mark.parametrize("count", range(2, 10))
def test_start_hand_for_every_table_size(count: int) -> None:
    seats = tuple(range(count))
    players = table(seats, 100)
    game = start_hand(RULES, SESSION, players, Deck())
    assert isinstance(game, GameState)
    ext = game.extension
    assert isinstance(ext, TexasPublic)
    assert (game.game_type, game.rules_version) == ("texas_holdem", "test-1")
    assert game.public.status is GameStatus.IN_PROGRESS and game.public.state_version == 0
    spot = positions(seats, 0)
    assert (ext.button_seat, ext.small_blind_seat, ext.big_blind_seat) == (
        0,
        spot.small_blind,
        spot.big_blind,
    )
    committed = {s.seat: s.committed for s in ext.seats}
    assert committed[spot.small_blind] == 5 and committed[spot.big_blind] == 10
    assert sum(committed.values()) == ext.pot == 15 and ext.current_bet == 10
    assert sum(s.stack for s in ext.seats) + ext.pot == 100 * count  # points are conserved
    assert game.public.turn is not None and game.public.turn.player_id == pid(
        10 + spot.first_to_act
    )
    assert ext.street is Street.PRE_FLOP and ext.board == ()
    hands = [p.hand for p in game.private.players]
    assert all(len(hand) == 2 for hand in hands)
    every = [c for hand in hands for c in hand] + list(game.private.remaining_cards)
    assert len(every) == 52 == len(set(every))
    assert len(game.private.remaining_cards) == 52 - 2 * count


def test_deal_order_and_rotation_with_a_known_deck() -> None:
    # Deck order is AS KS QS JS 10S 9S ...; deal starts at the small blind, clockwise.
    for button, order in [(0, (1, 2, 0)), (1, (2, 0, 1)), (2, (0, 1, 2))]:
        game = start_hand_for_testing(RULES, SESSION, table((0, 1, 2)), fixed_deck(), button)
        assert isinstance(game, GameState)
        by_seat = {p.player_id: p.hand for p in game.private.players}
        first_round = [Card.from_code(code) for code in ("AS", "KS", "QS")]
        second_round = [Card.from_code(code) for code in ("JS", "10S", "9S")]
        for index, seat in enumerate(order):
            assert by_seat[pid(10 + seat)] == (first_round[index], second_round[index])
        assert game.private.remaining_cards[0] == Card.from_code("8S")


def test_heads_up_deals_from_the_button_who_is_also_the_small_blind() -> None:
    game = start_hand_for_testing(RULES, SESSION, table((3, 8)), fixed_deck(), 8)
    assert isinstance(game, GameState) and isinstance(game.extension, TexasPublic)
    assert game.extension.small_blind_seat == 8 and game.extension.big_blind_seat == 3
    assert game.public.turn is not None and game.public.turn.player_id == pid(18)
    by_seat = {p.player_id: p.hand for p in game.private.players}
    assert by_seat[pid(18)] == (Card.from_code("AS"), Card.from_code("QS"))
    assert by_seat[pid(13)] == (Card.from_code("KS"), Card.from_code("JS"))


def test_short_stacks_post_what_they_have_and_are_all_in() -> None:
    players = (
        Player(pid(10), "a", 0, 100),
        Player(pid(11), "b", 1, 3),  # small blind, cannot cover 5
        Player(pid(12), "c", 2, 10),  # big blind, covers exactly: all-in
    )
    game = start_hand(RULES, SESSION, players, Deck())
    assert isinstance(game, GameState) and isinstance(game.extension, TexasPublic)
    seats = {s.seat: s for s in game.extension.seats}
    assert (seats[1].committed, seats[1].stack, seats[1].all_in) == (3, 0, True)
    assert (seats[2].committed, seats[2].stack, seats[2].all_in) == (10, 0, True)
    assert game.extension.pot == 13 and game.extension.current_bet == 10
    assert game.public.turn is not None and game.public.turn.player_id == pid(10)  # seat 0 can act


def test_the_first_actor_skips_all_in_seats_and_may_not_exist() -> None:
    skip = (
        Player(pid(10), "a", 0, 100),
        Player(pid(11), "b", 1, 100),
        Player(pid(12), "c", 2, 10),
        Player(pid(13), "d", 3, 2),
    )
    game = start_hand(RULES, SESSION, skip, Deck(), 1)  # SB 2 (10 -> 5), BB 3 (2, all-in), first: 0
    assert isinstance(game, GameState) and game.public.turn is not None
    assert game.public.turn.player_id == pid(10)
    tiny = (Player(pid(10), "a", 0, 4), Player(pid(11), "b", 1, 6))
    nobody = start_hand(TexasRules("t", 10, 20, False), SESSION, tiny, Deck())
    assert isinstance(nobody, GameState) and nobody.public.turn is None


def test_expected_rejections_are_data() -> None:
    cases = [
        (table((0,)), None, "bad_player_count"),
        (table(tuple(range(10))), None, "bad_player_count"),
        ((Player(pid(10), "a", 0, 0), Player(pid(11), "b", 1, 50)), None, "zero_stack"),
        (table((0, 1, 2)), 7, "unknown_button"),
    ]
    for players, button, code in cases:
        error = start_hand(RULES, SESSION, players, Deck(), button)
        assert isinstance(error, GameError) and error.code == code
        assert "P0" not in error.message


def test_programming_errors_raise() -> None:
    players = table((0, 1, 2))
    with pytest.raises(TypeError):
        start_hand(cast(TexasRules, "rules"), SESSION, players, Deck())
    with pytest.raises(TypeError):
        start_hand(RULES, cast(UUID, "x"), players, Deck())
    with pytest.raises(TypeError):
        start_hand(RULES, SESSION, cast(tuple[Player, ...], list(players)), Deck())
    with pytest.raises(TypeError):
        start_hand(RULES, SESSION, cast(tuple[Player, ...], (*players, None)), Deck())
    with pytest.raises(TypeError):
        start_hand(RULES, SESSION, players, Deck(), cast(int, "0"))
    with pytest.raises(ValueError):  # duplicate seats are structural
        start_hand(RULES, SESSION, (*players, Player(pid(99), "x", 0, 50)), Deck())


def test_start_hand_requires_a_production_deck_but_the_testing_path_does_not() -> None:
    players = table((0, 1, 2))
    with pytest.raises(TestOnlyDeckError):
        start_hand(RULES, SESSION, players, fixed_deck())
    partial = Deck()
    partial.deal(1)
    with pytest.raises(ValueError, match="complete, undealt"):
        start_hand(RULES, SESSION, players, partial)
    with pytest.raises(TypeError):
        start_hand(RULES, SESSION, players, cast(Deck, [Card.from_code("AS")]))
    assert isinstance(start_hand_for_testing(RULES, SESSION, players, fixed_deck()), GameState)
    # a deck that failed to shuffle is refused too
    deck = Deck()
    from secrets import SystemRandom

    original = SystemRandom.shuffle
    try:
        SystemRandom.shuffle = lambda self, cards: (_ for _ in ()).throw(OSError("no entropy"))  # type: ignore[method-assign,assignment]
        with pytest.raises(OSError):
            deck.reset()
    finally:
        SystemRandom.shuffle = original  # type: ignore[method-assign]
    with pytest.raises(DeckUnavailableError):
        start_hand(RULES, SESSION, players, deck)
    assert require_production_deck(Deck()) is not None


def test_start_hand_leaves_players_untouched_and_orders_seats() -> None:
    shuffled = (
        Player(pid(12), "c", 6, 100),
        Player(pid(10), "a", 2, 100),
        Player(pid(11), "b", 4, 100),
    )
    game = start_hand(RULES, SESSION, shuffled, Deck())
    assert isinstance(game, GameState)
    assert [p.seat for p in game.public.players] == [2, 4, 6]
    assert all(p.points == 100 for p in game.public.players)  # starting stacks, not live chips
    assert game.private.players[0].player_id == pid(10)
    assert isinstance(game.extension, TexasPublic) and game.extension.button_seat == 2


def test_views_expose_only_the_viewers_cards_and_public_table_data() -> None:
    game = start_hand(RULES, SESSION, table((0, 1, 2, 3)), Deck())
    assert isinstance(game, GameState)
    for player in game.public.players:
        view = project_player_view(game, player.id)
        assert isinstance(view, PlayerView) and isinstance(view.extension, TexasPublic)
        mine = {p.player_id: p.hand for p in game.private.players}[player.id]
        assert view.private.hand == mine
        public_text = repr(view.public) + repr(asdict(view.extension)) + repr(view.extension)
        for other in game.private.players:
            cards = other.hand if other.player_id != player.id else ()
            for card in (*cards, *game.private.remaining_cards):
                assert not reveals_card(public_text, card)


def test_hand_module_is_framework_free_and_the_testing_path_is_not_exported() -> None:
    root = Path(__file__).resolve().parents[2] / "app" / "games" / "texas_holdem"
    forbidden = {"fastapi", "starlette", "sqlalchemy", "pydantic", "alembic", "random", "secrets"}
    for name in ("rules.py", "positions.py", "state.py", "hand.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
        assert not {str(m).split(".")[0] for m in modules} & forbidden
        assert not any(str(m).startswith("app.db") for m in modules)
    import app.games.texas_holdem as package

    assert "start_hand_for_testing" not in package.__all__
    assert not hasattr(package, "start_hand_for_testing")


def test_product_modules_do_not_define_rule_values() -> None:
    # The product has no default blinds or stacks; only the caller (and tests) supply them.
    source = (
        Path(__file__).resolve().parents[2] / "app" / "games" / "texas_holdem" / "rules.py"
    ).read_text(encoding="utf-8")
    assert "TexasRules(" not in source


def test_repeated_seats_are_rejected_even_when_the_button_is_valid() -> None:
    for call in (
        lambda: positions((1, 1, 2), 1),
        lambda: next_seat((3, 3), 3),
        lambda: initial_button((0, 0, 1)),
    ):
        with pytest.raises(ValueError, match="cannot repeat"):
            call()
