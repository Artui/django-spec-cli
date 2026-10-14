"""``render_result`` - what ``present`` returned, written as a table or as JSON Lines."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, TextIO

from django_service_specs.commands.render.render_json_lines import render_json_lines
from django_service_specs.commands.render.render_table import render_table
from django_service_specs.output.output import Output

# The column a value that is no row is shown under in a table.
_RESULT = "result"


def render_result(presented: Any, output: Output | None, stream: TextIO, *, table: bool) -> None:
    """Write ``presented`` to ``stream``, as a table when ``table`` and JSON Lines when not.

    ``presented`` is what
    [`present`][django_service_specs.dispatch.present.present] returned for a
    spec, and ``output`` what the spec declares (``spec.output()``), which
    gives a table its columns. Read in this order:

    - ``None``, what a service that returned nothing presents: **nothing is
      written**, in either format. A header over no rows would read as an
      empty list.
    - **a mapping**, one row: a one-row table, or one line.
    - **a string or bytes**, a scalar, though both are iterable: a string is
      never read as rows of its characters. Bytes are refused by the JSON
      encoder with ``TypeError``, as an HTTP response refuses them.
    - **any other iterable**, rows: a table, or one line each, streamed, so a
      generator is read one row at a time and nothing here turns it into a
      list. A member that is no mapping - a spec with no presenter listing
      plain values - is a row of one ``result`` column in a table, and its
      own JSON on its own line.
    - anything else, **a scalar**: a table of one ``result`` column and one
      row, or one line holding its JSON (``42``, ``"done"``, ``true``).

    A table reads every row before writing its first line; see
    [`render_table`][django_service_specs.commands.render.render_table.render_table]
    for its columns, cells and markings, and
    [`render_json_lines`][django_service_specs.commands.render.render_json_lines.render_json_lines]
    for the encoding. Only ``stream`` is written to.
    """
    if presented is None:
        return
    # A mapping and a string are both iterable, and each is one value rather
    # than a sequence of rows, so both are answered before the iterable check.
    # Three conditions in one branch arc, each held by its own test:
    # the ``str`` cases of test_a_scalar_is_a_result_column_or_one_line_of_its_json
    # (``str``), test_bytes_are_a_scalar_and_never_iterated_as_rows
    # (``bytes``), and the ``int`` cases of the first (no iterable, which
    # iterating would raise on).
    if isinstance(presented, Mapping):
        rows: Iterable[Any] = (presented,)
    elif isinstance(presented, str | bytes) or not isinstance(presented, Iterable):
        rows = (presented,)
        # A scalar has no declared field to sit under, whatever the spec
        # declares, so its table is the one ``result`` column.
        output = None
    else:
        rows = presented
    if table:
        render_table([_row(row) for row in rows], output, stream)
    else:
        render_json_lines(rows, stream)


def _row(row: Any) -> Mapping[str, Any]:
    return row if isinstance(row, Mapping) else {_RESULT: row}
