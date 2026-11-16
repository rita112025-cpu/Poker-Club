"""Start one Texas hold'em hand (P3-01): positions, blinds and hole cards. No betting yet.

Deal order is part of the rules version: one card at a time, starting at the small
blind and going clockwise, two rounds. A seat that cannot cover its blind posts all it
has and is all-in. The first actor is the nominal first seat, or the next seat clockwise
that can still act; if no seat can act the turn is None. start_hand requires a production
deck; start_hand_for_testing accepts any deck and exists for trusted tests only (a static
guard test keeps it out of application code).
"""

from uuid import UUID

from app.games.core.deck import Deck
from app.games.core.engine import require_production_deck
from app.games.core.models import (
    GameError,
    GameState,
    GameStatus,
    Player,
    PrivateGameData,
    PrivatePlayerData,
    PublicGameData,
    Turn,
)
from app.games.core.validation import require_exact, require_exact_tuple, require_uuid
from app.games.texas_holdem.positions import (
    MAX_PLAYERS,
    MIN_PLAYERS,
    initial_button,
    next_seat,
    positions,
)
from app.games.texas_holdem.rules import TexasRules
from app.games.texas_holdem.state import SeatState, Street, TexasPublic

GAME_TYPE = "texas_holdem"
BAD_PLAYER_COUNT = "bad_player_count"
ZERO_STACK = "zero_stack"
UNKNOWN_BUTTON = "unknown_button"


def _first_actor(seats: tuple[int, ...], nominal: int, stacks: dict[int, int]) -> int | None:
    seat = nominal
    for _ in range(len(seats)):
        if stacks[seat] > 0:
            return seat
        seat = next_seat(seats, seat)
    return None


def _start(
    rules: TexasRules,
    session_id: UUID,
    players: tuple[Player, ...],
    deck: Deck,
    button_seat: int | None,
) -> GameState | GameError:
    require_exact(rules, TexasRules, "rules")
    require_uuid(session_id, "session_id")
    require_exact_tuple(players, Player, "players")
    require_exact(deck, Deck, "deck")
    if button_seat is not None and type(button_seat) is not int:
        raise TypeError("button_seat must be an integer or None")
    if not MIN_PLAYERS <= len(players) <= MAX_PLAYERS:
        return GameError(BAD_PLAYER_COUNT, "A hand needs 2 to 9 players")
    if any(player.points < 1 for player in players):
        return GameError(ZERO_STACK, "Every player needs at least one point")

    ordered = tuple(sorted(players, key=lambda player: player.seat))
    seats = tuple(player.seat for player in ordered)
    button = initial_button(seats) if button_seat is None else button_seat
    if button not in seats:
        return GameError(UNKNOWN_BUTTON, "The button must be an occupied seat")
    spots = positions(seats, button)

    posted = dict.fromkeys(seats, 0)
    stacks = {player.seat: player.points for player in ordered}
    blinds = ((spots.small_blind, rules.small_blind), (spots.big_blind, rules.big_blind))
    for seat, amount in blinds:
        paid = min(amount, stacks[seat])
        posted[seat] = paid
        stacks[seat] -= paid

    # Deal order: from the small blind clockwise, one card each, two rounds.
    order = [spots.small_blind]
    while len(order) < len(seats):
        order.append(next_seat(seats, order[-1]))
    cards = deck.deal(2 * len(seats))
    by_seat = {seat: (cards[i], cards[len(seats) + i]) for i, seat in enumerate(order)}
    remaining = deck.deal(deck.remaining_count)

    actor = _first_actor(seats, spots.first_to_act, stacks)
    turn_player = next((p.id for p in ordered if p.seat == actor), None)
    seat_states = tuple(
        SeatState(
            player.seat,
            player.id,
            stacks[player.seat],
            posted[player.seat],
            stacks[player.seat] == 0,
            False,
            posted[player.seat],
            False,
        )
        for player in ordered
    )
    extension = TexasPublic(
        Street.PRE_FLOP,
        button,
        spots.small_blind,
        spots.big_blind,
        seat_states,
        (),
        sum(posted.values()),
        max(posted.values()),
    )
    public = PublicGameData(
        GameStatus.IN_PROGRESS,
        0,
        ordered,
        None if turn_player is None else Turn(turn_player),
    )
    private = PrivateGameData(
        tuple(PrivatePlayerData(player.id, by_seat[player.seat]) for player in ordered),
        remaining,
    )
    return GameState(session_id, GAME_TYPE, rules.version, public, private, extension)


def start_hand(
    rules: TexasRules,
    session_id: UUID,
    players: tuple[Player, ...],
    deck: Deck,
    button_seat: int | None = None,
) -> GameState | GameError:
    """Production entry: the deck must be an exact, available, complete, shuffled Deck."""
    return _start(rules, session_id, players, require_production_deck(deck), button_seat)


def start_hand_for_testing(
    rules: TexasRules,
    session_id: UUID,
    players: tuple[Player, ...],
    deck: Deck,
    button_seat: int | None = None,
) -> GameState | GameError:
    """Trusted tests only: skips the production deck gate so fixed-order decks can be used."""
    return _start(rules, session_id, players, deck, button_seat)
