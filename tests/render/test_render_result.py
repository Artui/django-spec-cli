"""What ``present`` returned, written for a terminal or a pipe."""

from __future__ import annotations

import io
from collections.abc import Iterator, Mapping
from decimal import Decimal
from typing import Any

import pytest
from pydantic import BaseModel, Field

from django_service_specs.adapters.pydantic.pydantic_presenter import PydanticPresenter
from django_service_specs.commands.render.render_result import render_result
from django_service_specs.output.field_marking import FieldMarking
from django_service_specs.output.output import Output, OutputField

_OUTPUT = Output(
    (
        OutputField("id", "integer"),
        OutputField("title", "string"),
        OutputField("etag", "string", marking=FieldMarking.hidden()),
    )
)


def _render(presented: Any, output: Output | None, *, table: bool) -> str:
    stream = io.StringIO()
    render_result(presented, output, stream, table=table)
    return stream.getvalue()


def test_a_list_of_rows_is_a_table_or_a_line_each() -> None:
    rows = [{"id": 1, "title": "a", "etag": "x"}, {"id": 2, "title": "b", "etag": "y"}]
    assert _render(rows, _OUTPUT, table=True) == "id  title\n 1  a\n 2  b\n"
    # A pipe gets every presented field, the hidden one included, as an HTTP
    # response does: a marking shapes what an agent is shown, not what leaves.
    assert _render(rows, _OUTPUT, table=False) == (
        '{"id":1,"title":"a","etag":"x"}\n{"id":2,"title":"b","etag":"y"}\n'
    )


def test_a_single_row_is_a_one_row_table_or_one_line() -> None:
    row = {"id": 1, "title": "a", "etag": "x"}
    assert _render(row, _OUTPUT, table=True) == "id  title\n 1  a\n"
    assert _render(row, _OUTPUT, table=False) == '{"id":1,"title":"a","etag":"x"}\n'


def test_an_empty_list_is_a_header_or_nothing() -> None:
    assert _render([], _OUTPUT, table=True) == "id  title\n"
    assert _render([], _OUTPUT, table=False) == ""


@pytest.mark.parametrize("table", [True, False], ids=["table", "json"])
def test_nothing_presented_prints_nothing(table: bool) -> None:
    # ``None`` is what a service that returned nothing presents, and a header
    # over no rows would read as an empty list.
    assert _render(None, _OUTPUT, table=table) == ""


@pytest.mark.parametrize(
    ("value", "table", "expected"),
    [
        (42, True, "result\n42\n"),
        (42, False, "42\n"),
        ("done", True, "result\ndone\n"),
        ("done", False, '"done"\n'),
        (True, True, "result\ntrue\n"),
        (True, False, "true\n"),
    ],
    ids=["int-table", "int-json", "str-table", "str-json", "bool-table", "bool-json"],
)
def test_a_scalar_is_a_result_column_or_one_line_of_its_json(
    value: Any, table: bool, expected: str
) -> None:
    # A string is iterable, and is never read as rows of its characters.
    assert _render(value, None, table=table) == expected


def test_a_scalar_is_its_own_column_under_a_declared_output_too() -> None:
    # A service declaring rows can still present a bare value; the declared
    # header over one empty row would hide it.
    assert _render(42, _OUTPUT, table=True) == "result\n42\n"


@pytest.mark.parametrize("table", [True, False], ids=["table", "json"])
def test_bytes_are_a_scalar_and_never_iterated_as_rows(table: bool) -> None:
    # Bytes iterate as integers, so read as rows they would print one number
    # per byte. As a scalar they are refused by the encoder, as an HTTP
    # response refuses them, and nothing is written.
    stream = io.StringIO()
    with pytest.raises(TypeError, match="bytes"):
        render_result(b"ab", None, stream, table=table)
    assert stream.getvalue() == ""


def test_a_list_of_scalars_is_a_result_column_or_a_line_each() -> None:
    # What a spec with no presenter presents for a list of values.
    assert _render([3, "x", None], None, table=True) == "result\n3\nx\n\n"
    assert _render([3, "x", None], None, table=False) == '3\n"x"\nnull\n'


def test_rows_from_a_generator_stream_to_a_pipe() -> None:
    # Streaming has to survive this layer as well as the writer beneath it:
    # nothing here may turn the rows into a list, or look at the first one
    # before writing it.
    pulled = 0
    pulled_at_first_write: list[int] = []

    def rows() -> Iterator[Mapping[str, Any]]:
        nonlocal pulled
        for n in range(3):
            pulled += 1
            yield {"id": n}

    class _Recording(io.StringIO):
        def write(self, text: str) -> int:
            if not pulled_at_first_write:
                pulled_at_first_write.append(pulled)
            return super().write(text)

    stream = _Recording()
    render_result(rows(), _OUTPUT, stream, table=False)
    assert pulled_at_first_write == [1]
    assert stream.getvalue() == '{"id":0}\n{"id":1}\n{"id":2}\n'


def test_rows_from_a_generator_are_a_table_too() -> None:
    def rows() -> Iterator[Mapping[str, Any]]:
        yield {"id": 1, "title": "a"}
        yield {"id": 2, "title": "b"}

    assert _render(rows(), _OUTPUT, table=True) == "id  title\n 1  a\n 2  b\n"


class _Invoice(BaseModel):
    number: str = Field(title="No.")
    total: Decimal
    paid: bool


def test_a_pydantic_presenter_s_rows_render_under_its_own_output() -> None:
    # The row shape the kernel produces from a model: a title as the header,
    # a Decimal as the string its JSON mode writes.
    presenter = PydanticPresenter(_Invoice)
    rows = [
        presenter.present(_Invoice(number="A-1", total=Decimal("9.50"), paid=True)),
        presenter.present(_Invoice(number="A-22", total=Decimal("120.00"), paid=False)),
    ]
    assert _render(rows, presenter.output(), table=True) == (
        "No.   total   paid\nA-1   9.50    true\nA-22  120.00  false\n"
    )
    assert _render(rows, presenter.output(), table=False) == (
        '{"number":"A-1","total":"9.50","paid":true}\n'
        '{"number":"A-22","total":"120.00","paid":false}\n'
    )
