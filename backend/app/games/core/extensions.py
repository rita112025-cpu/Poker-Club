"""P3-00 game-specific public data and event payloads, by composition and allowlist.

GameState/PlayerView carry one optional public extension and GameEvent one optional
payload. Both accept only classes explicitly registered here, matched by EXACT type
(never isinstance), so a subclass of a registered class cannot smuggle extra
attributes into asdict()/repr() (the P2-B/R2 lesson). A registered class must be a
frozen, slotted dataclass that defines __post_init__ (its own exact-type validation) and
subclass the marker base. Registration is trusted startup code, like the engine registry;
it is not a protection against arbitrary same-process code.
"""

from dataclasses import is_dataclass


class PublicExtension:
    """Marker base for public, per-game table data (board, pot, bets, ...). Never private."""

    __slots__ = ()


class EventPayload:
    """Marker base for per-game event content; visibility still comes from the GameEvent."""

    __slots__ = ()


_PUBLIC_EXTENSIONS: set[type] = set()
_EVENT_PAYLOADS: set[type] = set()


def _register[T: type](base: type, registry: set[type], cls: T) -> T:
    if not isinstance(cls, type) or cls is base or not issubclass(cls, base):
        raise TypeError(f"class must be a strict subclass of {base.__name__}")
    if not is_dataclass(cls):
        raise TypeError("class must be a dataclass")
    params = getattr(cls, "__dataclass_params__", None)
    if params is None or not params.frozen:
        raise ValueError("class must be a frozen dataclass")
    if "__slots__" not in cls.__dict__:
        raise ValueError("class must use slots=True")
    if "__post_init__" not in cls.__dict__:
        raise ValueError("class must define its own __post_init__ validation")
    if cls in registry:
        raise ValueError("class is already registered")
    registry.add(cls)
    return cls


def register_public_extension[T: type](cls: T) -> T:
    """Class decorator; apply above @dataclass(frozen=True, slots=True)."""
    return _register(PublicExtension, _PUBLIC_EXTENSIONS, cls)


def register_event_payload[T: type](cls: T) -> T:
    return _register(EventPayload, _EVENT_PAYLOADS, cls)


def registered_public_extensions() -> frozenset[type]:
    return frozenset(_PUBLIC_EXTENSIONS)


def registered_event_payloads() -> frozenset[type]:
    return frozenset(_EVENT_PAYLOADS)


def check_public_extension(value: object, name: str) -> None:
    if value is not None and type(value) not in _PUBLIC_EXTENSIONS:
        raise TypeError(f"{name} must be None or an exact registered public extension")


def check_event_payload(value: object, name: str) -> None:
    if value is not None and type(value) not in _EVENT_PAYLOADS:
        raise TypeError(f"{name} must be None or an exact registered event payload")
