"""JSON Lines for a pipe: one object per line, streamed."""

from __future__ import annotations

import datetime as dt
import io
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from django.core.management.base import OutputWrapper
from django.utils.translation import gettext_lazy
from django_service_specs import UNSET, DataclassPresenter, UnsetType

from django_spec_cli.render.render_json_lines import render_json_lines
from tests.render.utils import pulled_before_the_first_write


def _written(rows: list[Any]) -> str:
    stream = io.StringIO()
    render_json_lines(rows, stream)
    return stream.getvalue()


def _lines(rows: list[Any]) -> list[str]:
    # ``split("\n")`` rather than ``splitlines()``, which also splits on the
    # separators JSON leaves raw, so it would read lines no JSON Lines reader does.
    text = _written(rows)
    assert text.endswith("\n")
    return text[:-1].split("\n")


def test_each_row_is_one_line_of_json() -> None:
    assert (
        _written([{"id": 1, "title": "a"}, {"id": 2, "title": "b"}])
        == '{"id":1,"title":"a"}\n{"id":2,"title":"b"}\n'
    )


def test_key_order_is_the_row_s_own() -> None:
    assert list(json.loads(_written([{"z": 1, "a": 2, "m": 3}]))) == ["z", "a", "m"]


def test_text_is_written_as_itself_rather_than_escaped() -> None:
    assert _lines([{"city": "Zürich", "name": "東京"}]) == ['{"city":"Zürich","name":"東京"}']


def test_values_json_has_no_type_for_are_encoded_as_django_encodes_them() -> None:
    key = uuid.UUID("12345678-1234-5678-1234-567812345678")
    [line] = _lines(
        [
            {
                "price": Decimal("12.50"),
                "at": dt.datetime(2024, 6, 1, 12, 0, tzinfo=dt.timezone.utc),
                "on": dt.date(2024, 6, 1),
                "key": key,
                "status": gettext_lazy("Draft"),
            }
        ]
    )
    assert json.loads(line) == {
        "price": "12.50",
        "at": "2024-06-01T12:00:00Z",
        "on": "2024-06-01",
        "key": "12345678-1234-5678-1234-567812345678",
        "status": "Draft",
    }


def test_a_line_separator_inside_a_value_never_ends_a_line() -> None:
    # JSON escapes the C0 controls and leaves U+2028, U+2029 and NEL raw, all
    # three of which some line readers break on. Each is escaped, so every
    # reader sees the row as one line and decodes the same value.
    value = "a b c\x85d\ne"
    (line,) = _written([{"note": value}]).splitlines()
    assert json.loads(line) == {"note": value}


def test_rows_are_streamed_one_at_a_time() -> None:
    # A generator of rows is a LIST selector's queryset being read: turning it
    # into a list first would hold every row in memory before the first byte.
    pulled, written = pulled_before_the_first_write(render_json_lines)
    assert pulled == 1
    assert written == '{"id":0}\n{"id":1}\n{"id":2}\n'


def test_no_rows_write_nothing() -> None:
    assert _written([]) == ""


def test_each_line_is_one_write_so_django_s_wrapper_adds_no_blank_lines() -> None:
    # ``OutputWrapper.write`` appends a newline to a message not ending in one,
    # so a line written in pieces would come out broken across lines.
    inner = io.StringIO()
    render_json_lines([{"a": 1}, {"a": 2}], OutputWrapper(inner))
    assert inner.getvalue() == '{"a":1}\n{"a":2}\n'


@dataclass
class _Note:
    id: int
    body: str | None
    bio: str | UnsetType = UNSET


def test_a_dataclass_presenter_s_rows_keep_an_absent_key_absent_and_a_null_null() -> None:
    # The row shape the kernel produces. A table shows both as an empty cell;
    # a pipe is where the two are told apart.
    presenter = DataclassPresenter(_Note)
    rows = [
        presenter.present(SimpleNamespace(id=1, body=None, bio=UNSET)),
        presenter.present(SimpleNamespace(id=2, body="b", bio="x")),
    ]
    assert _lines(rows) == ['{"id":1,"body":null}', '{"id":2,"body":"b","bio":"x"}']
