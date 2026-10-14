"""Whether a command's result is a table: the flag, then the setting, then the stream."""

from __future__ import annotations

import io
from typing import Any

import pytest
from django.core.management.base import OutputWrapper
from django.test import override_settings

from django_service_specs.commands.render.wants_table import wants_table


class _Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


class _NoIsatty:
    """A stream that writes and has no way to say whether it is a terminal."""

    def write(self, text: str) -> int:
        return len(text)


def test_a_terminal_gets_a_table_and_a_pipe_gets_json_lines() -> None:
    assert wants_table(_Terminal(), requested=None) is True
    assert wants_table(io.StringIO(), requested=None) is False


def test_the_stream_django_hands_a_command_is_asked_through_its_wrapper() -> None:
    # ``BaseCommand.stdout`` is an ``OutputWrapper``, and that is the object a
    # command passes here, so its answer has to be the wrapped stream's.
    assert wants_table(OutputWrapper(_Terminal()), requested=None) is True
    assert wants_table(OutputWrapper(io.StringIO()), requested=None) is False


def test_a_stream_that_cannot_say_is_not_a_terminal() -> None:
    # Holds the first condition of the tty guard: without it, ``None()`` raises.
    stream: Any = _NoIsatty()
    assert wants_table(stream, requested=None) is False


@pytest.mark.parametrize(
    ("requested", "setting", "terminal", "expected"),
    [
        # The flag beats the setting.
        ("json", "table", True, False),
        ("table", "json", False, True),
        # The flag beats the stream.
        ("json", "auto", True, False),
        ("table", "auto", False, True),
        # The setting beats the stream.
        (None, "json", True, False),
        (None, "table", False, True),
    ],
    ids=[
        "flag-json-over-setting-table",
        "flag-table-over-setting-json",
        "flag-json-over-terminal",
        "flag-table-over-pipe",
        "setting-json-over-terminal",
        "setting-table-over-pipe",
    ],
)
def test_the_flag_beats_the_setting_and_the_setting_beats_the_stream(
    requested: Any, setting: str, terminal: bool, expected: bool
) -> None:
    stream = _Terminal() if terminal else io.StringIO()
    with override_settings(SERVICE_SPECS_COMMAND_OUTPUT=setting):
        assert wants_table(stream, requested=requested) is expected


def test_a_flag_is_answered_without_reading_a_misconfigured_setting() -> None:
    # The setting is read only when no flag decides, so a bad value in it does
    # not stop an operator who has said which format they want.
    with override_settings(SERVICE_SPECS_COMMAND_OUTPUT="TABLE"):
        assert wants_table(io.StringIO(), requested="table") is True
