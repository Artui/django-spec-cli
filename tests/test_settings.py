"""The kernel's own settings, read at the call so ``override_settings`` and a late configure both reach them."""

from __future__ import annotations

from typing import Any

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from django_service_specs.settings import command_output, max_array_length


def test_the_default_maximum_is_a_thousand_elements() -> None:
    # Django's own DATA_UPLOAD_MAX_NUMBER_FIELDS, the line a form body stops at.
    assert max_array_length() == 1000


@pytest.mark.parametrize("value", [0, 1, 50_000, None])
def test_the_setting_is_read_as_given(value: int | None) -> None:
    with override_settings(SERVICE_SPECS_MAX_ARRAY_LENGTH=value):
        assert max_array_length() == value


@pytest.mark.parametrize(
    "value", [True, -1, 1.5, "1000"], ids=["bool", "negative", "float", "string"]
)
def test_a_setting_that_is_no_count_is_refused_by_name(value: Any) -> None:
    # Refused where it is read rather than compared, so a string never reaches
    # ``len(value) > "1000"`` as a TypeError naming nothing.
    with (
        override_settings(SERVICE_SPECS_MAX_ARRAY_LENGTH=value),
        pytest.raises(
            ImproperlyConfigured,
            match=f"SERVICE_SPECS_MAX_ARRAY_LENGTH must be a non-negative int or None; got {value!r}",
        ),
    ):
        max_array_length()


def test_a_command_s_output_is_chosen_by_its_stream_when_nothing_is_set() -> None:
    assert command_output() == "auto"


@pytest.mark.parametrize("value", ["auto", "table", "json"])
def test_the_command_output_setting_is_read_as_given(value: str) -> None:
    with override_settings(SERVICE_SPECS_COMMAND_OUTPUT=value):
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
        override_settings(SERVICE_SPECS_COMMAND_OUTPUT=value),
        pytest.raises(
            ImproperlyConfigured,
            match=(
                "SERVICE_SPECS_COMMAND_OUTPUT must be one of 'auto', 'table' or 'json'; "
                f"got {value!r}"
            ),
        ),
    ):
        command_output()
