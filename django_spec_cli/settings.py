"""The Django settings the kernel reads, each read at the call rather than at import."""

from __future__ import annotations

from typing import Any, Literal

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

_MAX_ARRAY_LENGTH = "SERVICE_SPECS_MAX_ARRAY_LENGTH"
# Django's own ``DATA_UPLOAD_MAX_NUMBER_FIELDS``: the line a form body already
# stops at, which a comma-separated query value and a JSON list both pass by.
_DEFAULT_MAX_ARRAY_LENGTH = 1000


def max_array_length() -> int | None:
    """``SERVICE_SPECS_MAX_ARRAY_LENGTH``: the most elements an array takes where it declares no maximum.

    1000 when the project sets nothing, and ``None`` where it sets ``None``,
    which bounds no array. It bounds every array ``Parameter`` with no
    ``max_length`` of its own, and a ``many`` call's list of rows, since a list
    is checked whole before any element is read and a long one otherwise costs
    a parse, a check and a Validator run per element - and, through an ``in``
    lookup, a query past the database's variable limit.

    Read on every call, never at import: specs are built at import, before a
    project's settings may be configured, and a test's ``override_settings``
    must reach a spec built before it.

    Raises:
        ImproperlyConfigured: a value that is no count - a ``bool``, a negative
            number, anything but an ``int`` or ``None`` - named here rather than
            failing as a comparison that names nothing.
    """
    value: Any = getattr(settings, _MAX_ARRAY_LENGTH, _DEFAULT_MAX_ARRAY_LENGTH)
    # One branch to coverage, each condition held by its own case of
    # test_a_setting_that_is_no_count_is_refused_by_name: [bool] the type
    # (``True`` is an ``int`` to ``isinstance``), [string] the type again, and
    # [negative] the sign; test_the_setting_is_read_as_given[None] holds the
    # ``None``, which without its condition is refused as no int.
    if value is not None and not (type(value) is int and value >= 0):
        raise ImproperlyConfigured(
            f"{_MAX_ARRAY_LENGTH} must be a non-negative int or None; got {value!r}. It is the "
            "most elements an array takes where its parameter declares no max_length."
        )
    return value


_COMMAND_OUTPUT = "SERVICE_SPECS_COMMAND_OUTPUT"
_COMMAND_OUTPUTS = ("auto", "table", "json")


def command_output() -> Literal["auto", "table", "json"]:
    """``SERVICE_SPECS_COMMAND_OUTPUT``: the format a ``SpecCommand`` writes its result in.

    ``"auto"`` when the project sets nothing: a table on a terminal and JSON
    Lines on anything else, so a person reads one and a script parses the
    other. ``"table"`` or ``"json"`` pins the format project-wide, for a
    project whose CI should print what an interactive run does. A command's
    own ``--table`` or ``--json`` still wins over either.

    Read on every call, never at import, as every kernel setting is.

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
