from __future__ import annotations

from typing import Any, Literal

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

_COMMAND_OUTPUT = "SPEC_CLI_OUTPUT"
_COMMAND_OUTPUTS = ("auto", "table", "json")


def command_output() -> Literal["auto", "table", "json"]:
    """``SPEC_CLI_OUTPUT``: the format a ``SpecCommand`` writes its result in."""
    value: Any = getattr(settings, _COMMAND_OUTPUT, "auto")
    if value not in _COMMAND_OUTPUTS:
        raise ImproperlyConfigured(
            f"{_COMMAND_OUTPUT} must be one of 'auto', 'table' or 'json'; got {value!r}. It is "
            "the format a SpecCommand writes its result in."
        )
    return value
