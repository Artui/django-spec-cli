from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, TextIO

from django_spec_cli.render.utils import compact_json

# JSON escapes every C0 control character and leaves these three raw. Each is
# a line break to some readers - Python's ``str.splitlines`` among them - so a
# value carrying one would end a line where the JSON Lines format says no line
# ends. They can only occur inside a JSON string, so replacing them in the
# encoded text changes no structure and decodes to the same value.
_LINE_BREAKS = {" ": "\\u2028", " ": "\\u2029", "\x85": "\\u0085"}


def render_json_lines(rows: Iterable[Mapping[str, Any]], stream: TextIO) -> None:
    """Write each row to ``stream`` as one line of JSON."""
    for row in rows:
        line = compact_json(row)
        for raw, escaped in _LINE_BREAKS.items():
            line = line.replace(raw, escaped)
        stream.write(line + "\n")
