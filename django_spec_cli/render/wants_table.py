from __future__ import annotations

from typing import Literal, TextIO

from django_spec_cli.settings import command_output


def wants_table(stream: TextIO, *, requested: Literal["table", "json"] | None) -> bool:
    """Whether to write a table to ``stream`` rather than JSON Lines."""
    choice = requested if requested is not None else command_output()
    if choice == "auto":
        isatty = getattr(stream, "isatty", None)
        return isatty is not None and bool(isatty())
    return choice == "table"
