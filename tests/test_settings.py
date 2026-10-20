"""The package's setting, read at the call so ``override_settings`` and a late configure both reach it."""

from __future__ import annotations

from typing import Any

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from django_spec_cli.settings import command_output


def test_a_command_s_output_is_chosen_by_its_stream_when_nothing_is_set() -> None:
    assert command_output() == "auto"


@pytest.mark.parametrize("value", ["auto", "table", "json"])
def test_the_command_output_setting_is_read_as_given(value: str) -> None:
    with override_settings(SPEC_CLI_OUTPUT=value):
        assert command_output() == value


@pytest.mark.parametrize(
    "value",
    ["TABLE", "jsonl", "", None, True],
    ids=["case", "unknown", "empty", "none", "bool"],
)
def test_a_command_output_that_names_no_format_is_refused_by_name(value: Any) -> None:
    # Matched exactly: a spelling a reader of settings.py would take for one of
    # the three is still refused, rather than quietly read as the default.
    with (
        override_settings(SPEC_CLI_OUTPUT=value),
        pytest.raises(
            ImproperlyConfigured,
            match=(f"SPEC_CLI_OUTPUT must be one of 'auto', 'table' or 'json'; got {value!r}"),
        ),
    ):
        command_output()
