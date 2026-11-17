from __future__ import annotations

import json
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from django_service_specs import FieldAudience, Output, OutputField

# Unicode categories that move the cursor or the line rather than print: the
# C0 and C1 controls (newline, tab, the escape that starts a terminal
# sequence) and the line and paragraph separators. Written escaped, so a row
# can neither split itself across two lines nor drive the operator's terminal.
_BREAKING = frozenset({"Cc", "Zl", "Zp"})
_NUMERIC = frozenset({"integer", "number"})


@dataclass(frozen=True)
class TableColumn:
    """One column of a table: the row key it reads, its header, and how its cells read."""

    name: str
    header: str
    right: bool = False
    # ``None`` where the value is shown as presented: no choices declared, or a handle.
    choices: tuple[tuple[Any, Any], ...] | None = None


def compact_json(value: Any) -> str:
    """``value`` as compact JSON, its text written as itself, as ``DjangoJSONEncoder`` does."""
    return json.dumps(value, cls=DjangoJSONEncoder, ensure_ascii=False, separators=(",", ":"))


def table_columns(
    rows: Sequence[Mapping[str, Any]], output: Output | None
) -> tuple[TableColumn, ...]:
    """``output``'s fields but the hidden, or the first row's keys when there is none."""
    if output is None:
        return tuple(TableColumn(str(key), _text(str(key))) for key in rows[0]) if rows else ()
    return tuple(_column(field) for field in output if _audience(field) is not FieldAudience.HIDDEN)


def table_cell(value: Any, choices: tuple[tuple[Any, Any], ...] | None) -> str:
    """A cell as a table shows it: a choice's display, else JSON with a string's quotes left off."""
    if value is None:
        return ""
    if choices is not None:
        value = _display(value, choices)
    if isinstance(value, str):
        return _text(value)
    encoded = compact_json(value)
    return _text(json.loads(encoded) if encoded.startswith('"') else encoded)


def _audience(field: OutputField) -> FieldAudience | None:
    # ``None`` for an unmarked field, which has no audience to read.
    return None if field.marking is None else field.marking.audience


def _column(field: OutputField) -> TableColumn:
    # Only a handle keeps its value, not every marked field.
    return TableColumn(
        field.name,
        _text(field.name if field.label is None else str(field.label)),
        right=field.type in _NUMERIC,
        choices=None if _audience(field) is FieldAudience.HANDLE else field.choices,
    )


def _display(value: Any, choices: tuple[tuple[Any, Any], ...]) -> Any:
    """The display of the choice ``value`` names, or ``value`` itself."""
    if isinstance(value, list | tuple):
        return [_display(member, choices) for member in value]
    return next(
        (display for choice, display in choices if type(choice) is type(value) and choice == value),
        value,
    )


def _text(value: str) -> str:
    return "".join(
        char.encode("unicode_escape").decode("ascii")
        if unicodedata.category(char) in _BREAKING
        else char
        for char in value
    )
