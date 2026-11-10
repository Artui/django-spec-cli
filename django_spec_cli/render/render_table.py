from __future__ import annotations

import json
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TextIO

from django_service_specs import FieldAudience, Output, OutputField

from django_spec_cli.render.utils import compact_json

# Two spaces between columns: one reads as a space inside a value.
_GAP = "  "
# Unicode categories that move the cursor or the line rather than print: the
# C0 and C1 controls (newline, tab, the escape that starts a terminal
# sequence) and the line and paragraph separators. Written escaped, so a row
# can neither split itself across two lines nor drive the operator's terminal.
_BREAKING = frozenset({"Cc", "Zl", "Zp"})
_NUMERIC = frozenset({"integer", "number"})
# East Asian wide and full-width: two terminal columns each.
_WIDE = frozenset({"W", "F"})
# Nonspacing and enclosing marks and format characters: drawn on or between
# their neighbours, so no column of their own. ``unicodedata.combining`` is
# not this test - it answers a canonical combining class, which a variation
# selector and an enclosing mark both have as zero.
_ZERO_WIDTH = frozenset({"Mn", "Me", "Cf"})


@dataclass(frozen=True)
class _Column:
    name: str
    header: str
    right: bool = False
    # ``None`` where the value is shown as presented: no choices declared, or a
    # handle, whose value is what the next command takes.
    choices: tuple[tuple[Any, Any], ...] | None = None


def render_table(rows: Sequence[Mapping[str, Any]], output: Output | None, stream: TextIO) -> None:
    """Write ``rows`` to ``stream`` as a table with a header line."""
    columns = _columns(rows, output)
    if not columns:
        return
    lines = [
        [_text(column.header) for column in columns],
        *([_cell(row.get(column.name), column.choices) for column in columns] for row in rows),
    ]
    widths = [max(_width(line[n]) for line in lines) for n in range(len(columns))]
    for line in lines:
        cells = (
            _pad(text, width, right=column.right)
            for text, width, column in zip(line, widths, columns, strict=True)
        )
        stream.write(_GAP.join(cells).rstrip() + "\n")


def _columns(rows: Sequence[Mapping[str, Any]], output: Output | None) -> tuple[_Column, ...]:
    if output is None:
        return tuple(_Column(str(key), str(key)) for key in rows[0]) if rows else ()
    return tuple(_column(field) for field in output if _audience(field) is not FieldAudience.HIDDEN)


def _audience(field: OutputField) -> FieldAudience | None:
    # ``None`` for an unmarked field, which has no audience to read.
    return None if field.marking is None else field.marking.audience


def _column(field: OutputField) -> _Column:
    # Only a handle keeps its value, not every marked field.
    return _Column(
        field.name,
        field.name if field.label is None else str(field.label),
        right=field.type in _NUMERIC,
        choices=None if _audience(field) is FieldAudience.HANDLE else field.choices,
    )


def _cell(value: Any, choices: tuple[tuple[Any, Any], ...] | None) -> str:
    if value is None:
        return ""
    if choices is not None:
        value = _display(value, choices)
    if isinstance(value, str):
        return _text(value)
    encoded = compact_json(value)
    # A value the encoder writes as a JSON string is shown without its quotes, as text is.
    return _text(json.loads(encoded) if encoded.startswith('"') else encoded)


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


def _width(text: str) -> int:
    return sum(
        0
        if unicodedata.category(char) in _ZERO_WIDTH
        else 2
        if unicodedata.east_asian_width(char) in _WIDE
        else 1
        for char in text
    )


def _pad(text: str, width: int, *, right: bool) -> str:
    fill = " " * (width - _width(text))
    return fill + text if right else text + fill
