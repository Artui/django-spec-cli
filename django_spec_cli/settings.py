"""The Django setting this package reads, read at the call rather than at import."""

from __future__ import annotations

from typing import Any, Literal

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

_COMMAND_OUTPUT = "SPEC_CLI_OUTPUT"
_COMMAND_OUTPUTS = ("auto", "table", "json")


def command_output() -> Literal["auto", "table", "json"]:
    """``SPEC_CLI_OUTPUT``: the format a ``SpecCommand`` writes its result in.

    ``"auto"`` when the project sets nothing: a table on a terminal and JSON
    Lines on anything else, so a person reads one and a script parses the
    other. ``"table"`` or ``"json"`` pins the format project-wide, for a
    project whose CI should print what an interactive run does. A command's
    own ``--table`` or ``--json`` still wins over either.

    Read on every call, never at import, as every setting the kernel reads is.

    Raises:
        ImproperlyConfigured: anything but one of the three strings, matched
            exactly, so ``"TABLE"`` or ``"jsonl"`` is refused by name rather
            than quietly read as the default.
    """
    value: Any = getattr(settings, _COMMAND_OUTPUT, "auto")
    if value not in _COMMAND_OUTPUTS:
        raise ImproperlyConfigured(
            f"{_COMMAND_OUTPUT} must be one of 'auto', 'table' or 'json'; got {value!r}. It is "
            "the format a SpecCommand writes its result in."
        )
    return value
