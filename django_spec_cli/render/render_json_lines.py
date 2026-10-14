"""``render_json_lines`` - presented rows as JSON Lines, one object per line, streamed."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any, TextIO

from django.core.serializers.json import DjangoJSONEncoder

# JSON escapes every C0 control character and leaves these three raw. Each is
# a line break to some readers - Python's ``str.splitlines`` among them - so a
# value carrying one would end a line where the JSON Lines format says no line
# ends. They can only occur inside a JSON string, so replacing them in the
# encoded text changes no structure and decodes to the same value.
_LINE_BREAKS = {" ": "\\u2028", " ": "\\u2029", "\x85": "\\u0085"}


def render_json_lines(rows: Iterable[Mapping[str, Any]], stream: TextIO) -> None:
    """Write each row to ``stream`` as one line of JSON.

    **Streamed**: each row is encoded and written before the next is read, so
    a generator over a large result is never held in memory whole. That is
    why the format is JSON Lines rather than one JSON array.

    Each row is written as it was presented: every key, in the row's own
    order, including a key no ``Output`` declares (the ``affordances``
    ``present`` adds) and a field marked hidden, which is how an HTTP response
    carries it too. Text is written as itself (``ensure_ascii=False``), and
    ``DjangoJSONEncoder`` encodes what JSON has no type for: a ``Decimal`` as
    its string, a date-time, date or time in ISO 8601, a ``UUID``, a lazy
    translation in the active language. A value the encoder refuses raises
    ``TypeError`` before its line is written.

    One ``write`` per line, each ending in ``"\\n"``: Django's
    ``OutputWrapper`` appends a newline to any message that does not end in
    one, so a line written in pieces would come out broken.
    """
    for row in rows:
        line = json.dumps(row, cls=DjangoJSONEncoder, ensure_ascii=False, separators=(",", ":"))
        for raw, escaped in _LINE_BREAKS.items():
            line = line.replace(raw, escaped)
        stream.write(line + "\n")
