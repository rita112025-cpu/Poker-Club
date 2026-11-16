"""Field-matrix checks every registered public extension / event payload must pass (P3-01-0).

A registered class has to validate EVERY field with exact types. For each class under
app/ there must be an entry in MATRICES naming the kind of every field; the enforcement
test fails when a registered class has no entry or an entry misses a field. Kinds:
text, uuid, int, nonneg_int, bool, enum, tuple (exact tuple). Value-specific rules and
nested dataclass elements go in extra_bad.
"""

from collections.abc import Callable
from dataclasses import dataclass, field, fields
from typing import Any
from uuid import UUID

import pytest


class _TextSub(str):
    secret = "MATRIX_SECRET"


class _IntSub(int):
    secret = "MATRIX_SECRET"


class _UuidSub(UUID):
    secret = "MATRIX_SECRET"


class _TupleSub(tuple):  # type: ignore[type-arg]
    secret = "MATRIX_SECRET"


@dataclass
class FieldMatrix:
    build: Callable[..., object]
    kinds: dict[str, str]
    extra_bad: dict[str, list[object]] = field(default_factory=dict)


MATRICES: dict[type, FieldMatrix] = {}


def attack_values(kind: str, valid: Any) -> list[object]:
    match kind:
        case "text":
            return [_TextSub("x"), b"x", 1, None, "  "]
        case "uuid":
            return [_UuidSub(int=1), "00000000-0000-0000-0000-000000000001", 1, None]
        case "int":
            return [_IntSub(1), True, 1.0, "1", None]
        case "nonneg_int":
            return [_IntSub(1), True, 1.0, "1", None, -1]
        case "bool":
            return [1, 0, "True", None]
        case "enum":
            return [None, "value", 1]
        case "tuple":
            return [_TupleSub(valid), list(valid), None, "x"]
    raise AssertionError(f"unknown field kind {kind!r}")


def check_field_matrix(cls: type, matrix: FieldMatrix) -> None:
    valid = matrix.build()
    assert type(valid) is cls, "build() must return an exact instance of the class"
    declared = {item.name for item in fields(cls)}  # type: ignore[arg-type]
    assert set(matrix.kinds) == declared, (
        f"matrix must name every field; missing {sorted(declared - set(matrix.kinds))}, "
        f"unknown {sorted(set(matrix.kinds) - declared)}"
    )
    for name, kind in matrix.kinds.items():
        bad_values = attack_values(kind, getattr(valid, name)) + matrix.extra_bad.get(name, [])
        for bad in bad_values:
            with pytest.raises((TypeError, ValueError)):
                matrix.build(**{name: bad})
