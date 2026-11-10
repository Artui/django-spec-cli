from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, TextIO

from django_service_specs import Output

from django_spec_cli.render.render_json_lines import render_json_lines
from django_spec_cli.render.render_table import render_table

# The column a value that is no row is shown under in a table.
_RESULT = "result"


def render_result(presented: Any, output: Output | None, stream: TextIO, *, table: bool) -> None:
    """Write ``presented`` to ``stream``, as a table when ``table`` and JSON Lines when not."""
    if presented is None:
        return
    if isinstance(presented, Mapping):
        rows: Iterable[Any] = (presented,)
    elif isinstance(presented, str | bytes) or not isinstance(presented, Iterable):
        rows = (presented,)
        output = None
    else:
        rows = presented
    if table:
        render_table([_row(row) for row in rows], output, stream)
    else:
        render_json_lines(rows, stream)


def _row(row: Any) -> Mapping[str, Any]:
    return row if isinstance(row, Mapping) else {_RESULT: row}
