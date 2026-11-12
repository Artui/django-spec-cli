from __future__ import annotations

from typing import Literal, TextIO

from django_spec_cli.settings import command_output


def wants_table(stream: TextIO, *, requested: Literal["table", "json"] | None) -> bool:
    """Whether to write a table to ``stream`` rather than JSON Lines.

    Three answers, the first that decides winning:

    1. ``requested``: what the operator asked for with ``--table`` or
       ``--json``. The setting is not read at all when the flag decides, so a
       misconfigured setting never overrides an explicit request.
    2. The project's ``SPEC_CLI_OUTPUT`` setting, when it pins
       ``"table"`` or ``"json"``.
    3. ``stream.isatty()``: a table for a person at a terminal, JSON Lines for
       a pipe, a file or a test's buffer. A stream with no ``isatty`` cannot
       say it is a terminal and gets JSON Lines.

    That third answer means an interactive run and CI print different things
    by default, which is why both the flag and the setting exist. Django's
    ``OutputWrapper``, which is what a command's ``self.stdout`` is, answers
    ``isatty`` for the stream it wraps.
    """
    choice = requested if requested is not None else command_output()
    if choice == "auto":
        isatty = getattr(stream, "isatty", None)
        return isatty is not None and bool(isatty())
    return choice == "table"
