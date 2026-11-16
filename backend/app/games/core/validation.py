"""Shared exact-type validators for models, extensions and payloads (P3-01-0).

Every check is `type(value) is X`, never isinstance: a subclass of str, int, UUID,
tuple, an Enum-like or a dataclass can carry extra attributes that asdict()/deepcopy()/
repr() would keep. Extension and payload classes must validate EVERY field with these (or
an equivalent) in their own __post_init__ and are covered by the field-matrix tests.
These helpers never convert values.
"""

from enum import Enum
from uuid import UUID


def require_exact(value: object, expected: type[object], name: str) -> None:
    if type(value) is not expected:
        raise TypeError(f"{name} must be an exact {expected.__name__} instance")


def require_text(value: object, name: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} cannot be blank")


def require_uuid(value: object, name: str) -> None:
    if type(value) is not UUID:
        raise TypeError(f"{name} must be a UUID")


def require_bool(value: object, name: str) -> None:
    if type(value) is not bool:
        raise TypeError(f"{name} must be a boolean")


def require_int(value: object, name: str) -> None:
    """Exact int (a bool is rejected); sign is the caller's decision."""
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")


def require_nonnegative_int(value: object, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} cannot be negative")


def require_enum(value: object, enum_type: type[Enum], name: str) -> None:
    if type(value) is not enum_type:
        raise TypeError(f"{name} must be a {enum_type.__name__} member")


def require_exact_tuple(value: object, expected: type[object], name: str) -> None:
    """Exact tuple whose every element is exactly `expected`."""
    if type(value) is not tuple:
        raise TypeError(f"{name} must be a tuple")
    if any(type(item) is not expected for item in value):
        raise TypeError(f"{name} contains an invalid element")
