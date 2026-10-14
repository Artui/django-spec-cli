"""A table for a terminal: columns from the declared ``Output``, never from a row."""

from __future__ import annotations

import datetime as dt
import io
import uuid
from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace
from typing import Annotated

import pytest
from django.core.management.base import OutputWrapper
from django.utils import translation
from django.utils.translation import gettext_lazy

from django_service_specs.adapters.dataclass.dataclass_presenter import DataclassPresenter
from django_service_specs.commands.render.render_table import render_table
from django_service_specs.output.field_marking import FieldMarking
from django_service_specs.output.output import Output, OutputField
from django_service_specs.types.field_audience import FieldAudience
from django_service_specs.types.unset import UNSET, UnsetType
from django_service_specs.types.value_formatter import ValueFormatter
from tests.adapter_app.models import Status

_STATUS = (("draft", "Draft"), ("published", "Published"))

_NOTES = Output(
    (
        OutputField("id", "integer", label="ID"),
        OutputField("title", "string"),
        OutputField("status", "string", choices=_STATUS),
        OutputField("note", "string", nullable=True),
    )
)


def _table(rows: list[dict[str, object]], output: Output | None) -> str:
    stream = io.StringIO()
    render_table(rows, output, stream)
    return stream.getvalue()


def test_columns_are_the_declared_fields_in_declaration_order() -> None:
    # Each row lists its keys in another order, and the columns do not follow.
    rows: list[dict[str, object]] = [
        {"note": None, "status": "draft", "title": "Hello", "id": 7},
        {"title": "Hi", "id": 12, "note": "x", "status": "published"},
    ]
    assert _table(rows, _NOTES) == (
        "ID  title  status     note\n 7  Hello  Draft\n12  Hi     Published  x\n"
    )


def test_an_empty_result_still_prints_the_header() -> None:
    assert _table([], _NOTES) == "ID  title  status  note\n"


def test_a_null_cell_is_empty_and_never_shifts_a_column() -> None:
    rows: list[dict[str, object]] = [
        {"id": 1, "title": None, "status": "draft", "note": "first"},
        {"id": 2, "title": "two", "status": None, "note": "second"},
    ]
    assert _table(rows, _NOTES) == (
        "ID  title  status  note\n 1         Draft   first\n 2  two            second\n"
    )


def test_a_key_a_row_leaves_out_is_an_empty_cell_like_a_null() -> None:
    # ``always_present=False`` is a key the presenter may omit, as a dataclass
    # does for ``UNSET``. A table cannot show the difference from a null, and
    # JSON Lines, which writes the row as it is, can.
    output = Output(
        (
            OutputField("id", "integer"),
            OutputField("bio", "string", always_present=False),
            OutputField("name", "string"),
        )
    )
    assert _table([{"id": 1, "name": "Ada"}], output) == "id  bio  name\n 1       Ada\n"


def test_a_header_is_the_label_and_else_the_name() -> None:
    output = Output(
        (
            OutputField("due_at", "string", label=gettext_lazy("Due")),
            OutputField("owner_id", "integer"),
        )
    )
    assert _table([], output) == "Due  owner_id\n"


def test_a_choice_is_shown_by_its_display_and_an_unknown_value_as_itself() -> None:
    # A stale row naming a choice since removed is still reported, as the
    # agent projection reports it.
    output = Output((OutputField("status", "string", choices=_STATUS),))
    assert _table([{"status": "published"}, {"status": "archived"}], output) == (
        "status\nPublished\narchived\n"
    )


def test_a_choice_display_is_read_in_the_active_language() -> None:
    output = Output((OutputField("status", "string", choices=((1, gettext_lazy("Yes")),)),))
    with translation.override("fr"):
        assert _table([{"status": 1}], output) == "status\nOui\n"


@pytest.mark.parametrize(
    "states",
    [["draft", "published", "gone"], ("draft", "published", "gone")],
    ids=["list", "tuple"],
)
def test_an_array_of_choices_is_shown_member_by_member(states: object) -> None:
    # Never looked up whole: the array is no choice, and its members are.
    output = Output((OutputField("states", "array", items="string", choices=_STATUS),))
    assert _table([{"states": states}], output) == ('states\n["Draft","Published","gone"]\n')


def test_a_handle_keeps_its_value_even_with_choices() -> None:
    # A handle is what the operator pastes into the next command, which takes
    # the value and not the display.
    output = Output(
        (OutputField("kind", "string", choices=_STATUS, marking=FieldMarking.handle()),)
    )
    assert _table([{"kind": "draft"}], output) == "kind\ndraft\n"


def test_a_label_with_choices_is_shown_by_its_display() -> None:
    # Only a handle keeps its value: any other marked field is displayed.
    output = Output((OutputField("kind", "string", choices=_STATUS, marking=FieldMarking.label()),))
    assert _table([{"kind": "draft"}], output) == "kind\nDraft\n"


def test_an_unmarked_field_without_choices_is_shown_as_presented() -> None:
    output = Output((OutputField("title", "string"),))
    assert _table([{"title": "draft"}], output) == "title\ndraft\n"


def test_a_hidden_field_is_no_column_and_every_other_audience_is_one() -> None:
    # ``HIDDEN`` is plumbing: the projection for an agent drops it, and a
    # table read by a person has no more use for it. ``LABEL``, ``HANDLE`` and
    # ``CONTENT`` are things a person reads or pastes, so each stays.
    output = Output(
        (
            OutputField("pk", "integer", marking=FieldMarking.handle()),
            OutputField("name", "string", marking=FieldMarking.label()),
            OutputField("etag", "string", marking=FieldMarking.hidden()),
            OutputField("body", "string", marking=FieldMarking(FieldAudience.CONTENT)),
            OutputField("plain", "string"),
        )
    )
    row: dict[str, object] = {"pk": 3, "name": "n", "etag": "e1", "body": "b", "plain": "p"}
    assert _table([row], output) == "pk  name  body  plain\n 3  n     b     p\n"


def test_an_agent_formatter_is_not_applied_to_a_table() -> None:
    # A marking's formatter is how an agent audience reads the value. A
    # command names no audience, and shows the value as presented, as HTTP does.
    shout = ValueFormatter(lambda value: str(value).upper(), "string")
    output = Output((OutputField("title", "string", marking=FieldMarking.formatted(shout)),))
    assert _table([{"title": "quiet"}], output) == "title\nquiet\n"


def test_a_key_the_output_does_not_declare_is_no_column() -> None:
    # ``present`` adds ``affordances`` to a row beside the declared fields.
    # The columns are the declaration's, so it stays out of the table; JSON
    # Lines writes the row whole and carries it.
    output = Output((OutputField("id", "integer"),))
    row: dict[str, object] = {"id": 1, "affordances": {"publish": {"available": True}}}
    assert _table([row], output) == "id\n 1\n"


def test_a_nested_value_is_one_compact_json_cell() -> None:
    output = Output(
        (
            OutputField(
                "address",
                "object",
                fields=Output((OutputField("city", "string"), OutputField("zip", "string"))),
            ),
            OutputField("tags", "array", items="string"),
            OutputField("name", "string"),
        )
    )
    row: dict[str, object] = {
        "address": {"city": "Oslo", "zip": None},
        "tags": ["a", "b"],
        "name": "x",
    }
    assert _table([row], output) == (
        'address                     tags       name\n{"city":"Oslo","zip":null}  ["a","b"]  x\n'
    )


def test_a_scalar_is_shown_unquoted_in_json_s_spelling() -> None:
    key = uuid.UUID("12345678-1234-5678-1234-567812345678")
    output = Output(
        (
            OutputField("ok", "boolean"),
            OutputField("price", "string"),
            OutputField("at", "string", format="date-time"),
            OutputField("key", "string"),
            OutputField("ratio", "number"),
        )
    )
    row: dict[str, object] = {
        "ok": False,
        "price": Decimal("12.50"),
        "at": dt.datetime(2024, 6, 1, 12, 0, tzinfo=dt.timezone.utc),
        "key": key,
        "ratio": 0.5,
    }
    assert _table([row], output) == (
        "ok     price  at                    key                                   ratio\n"
        "false  12.50  2024-06-01T12:00:00Z  12345678-1234-5678-1234-567812345678    0.5\n"
    )


def test_numbers_are_right_aligned_and_text_is_left_aligned() -> None:
    output = Output((OutputField("n", "number", label="Amount"), OutputField("s", "string")))
    assert _table([{"n": 3, "s": "a"}, {"n": 1234.5, "s": "bcd"}], output) == (
        "Amount  s\n     3  a\n1234.5  bcd\n"
    )


def test_no_line_ends_in_whitespace() -> None:
    output = Output((OutputField("a", "string"), OutputField("b", "string")))
    text = _table([{"a": "long value", "b": None}, {"a": "x", "b": "y  "}], output)
    assert all(line == line.rstrip() for line in text.split("\n"))
    assert text == "a           b\nlong value\nx           y\n"


def test_wide_and_zero_width_characters_are_measured_by_the_columns_they_take() -> None:
    # Each CJK ideograph takes two terminal columns, and a combining accent,
    # a variation selector and a zero-width joiner take none, so ``len``
    # would misalign every one of them. Written as escapes, so the source
    # shows which character each is.
    output = Output((OutputField("name", "string"), OutputField("n", "string")))
    rows: list[dict[str, object]] = [
        {"name": "\u6771\u4eac", "n": "1"},
        {"name": "Cafe\u0301", "n": "2"},
        {"name": "abc", "n": "3"},
        {"name": "\u2764\ufe0fa\u200db", "n": "4"},
    ]
    assert _table(rows, output) == (
        "name  n\n\u6771\u4eac  1\nCafe\u0301  2\nabc   3\n\u2764\ufe0fa\u200db   4\n"
    )


def test_with_no_output_a_key_used_as_a_header_is_escaped_too() -> None:
    # With no declared output the header is a row's own key.
    assert _table([{"a\nb": 1}], None) == "a\\nb\n1\n"


def test_a_line_break_or_control_character_in_a_cell_is_escaped() -> None:
    # A raw newline would split a row across two lines, and a raw escape byte
    # would let a row's contents drive the operator's terminal.
    output = Output((OutputField("note", "string"), OutputField("n", "string")))
    rows: list[dict[str, object]] = [{"note": "a\nb\tc\x1b[31m", "n": "1"}]
    assert _table(rows, output) == "note             n\na\\nb\\tc\\x1b[31m  1\n"


def test_with_no_output_the_first_row_names_the_columns() -> None:
    # The one case a row is read for its columns: a spec with no declared output.
    rows: list[dict[str, object]] = [{"b": 1, "a": "x"}, {"a": "y", "c": 9}]
    assert _table(rows, None) == "b  a\n1  x\n   y\n"


def test_with_no_output_and_no_rows_nothing_is_printed() -> None:
    assert _table([], None) == ""


def test_an_output_with_no_fields_prints_nothing() -> None:
    assert _table([{"a": 1}], Output()) == ""


def test_each_line_is_one_write_so_django_s_wrapper_adds_no_blank_lines() -> None:
    inner = io.StringIO()
    render_table(
        [{"id": 1, "title": "t", "status": "draft", "note": "n"}], _NOTES, OutputWrapper(inner)
    )
    assert inner.getvalue() == "ID  title  status  note\n 1  t      Draft   n\n"


@dataclass
class _Book:
    id: Annotated[int, FieldMarking.handle()]
    title: str
    status: Status
    price: Decimal
    published: dt.date | None
    etag: Annotated[str, FieldMarking.hidden()]
    subtitle: str | UnsetType = UNSET


def test_a_dataclass_presenter_s_rows_render_under_its_own_output() -> None:
    # The row shape the kernel produces, rather than one written for the test:
    # a Choices label, a Decimal as its string, a date in ISO 8601, an UNSET
    # key left out, and a hidden field the presenter still renders.
    presenter = DataclassPresenter(_Book)
    rows = [
        presenter.present(
            SimpleNamespace(
                id=1,
                title="Dune",
                status=Status.PUBLISHED,
                price=Decimal("9.99"),
                published=dt.date(1965, 8, 1),
                etag="x",
                subtitle=UNSET,
            )
        ),
        presenter.present(
            SimpleNamespace(
                id=22,
                title="Emma",
                status=Status.DRAFT,
                price=Decimal("12.50"),
                published=None,
                etag="y",
                subtitle="A Novel",
            )
        ),
    ]
    assert all("etag" in row for row in rows)
    assert _table(rows, presenter.output()) == (
        "id  title  status     price  published   subtitle\n"
        " 1  Dune   Published  9.99   1965-08-01\n"
        "22  Emma   Draft      12.50              A Novel\n"
    )


def test_a_line_or_paragraph_separator_in_a_cell_is_escaped() -> None:
    # JSON leaves both raw and ``str.splitlines`` breaks a line at either, so a
    # raw one would split a row for any reader that splits that way.
    output = Output((OutputField("note", "string"),))
    assert _table([{"note": "a\u2028b\u2029c"}], output) == "note\na\\u2028b\\u2029c\n"


def test_an_enclosing_mark_takes_no_column() -> None:
    output = Output((OutputField("name", "string"), OutputField("n", "string")))
    rows: list[dict[str, object]] = [{"name": "a\u20ddb", "n": "1"}, {"name": "ab", "n": "2"}]
    assert _table(rows, output) == "name  n\na\u20ddb    1\nab    2\n"


def test_a_full_width_character_takes_two_columns() -> None:
    output = Output((OutputField("name", "string"), OutputField("n", "string")))
    rows: list[dict[str, object]] = [{"name": "\uff21", "n": "1"}, {"name": "ab", "n": "2"}]
    assert _table(rows, output) == "name  n\n\uff21    1\nab    2\n"


def test_a_choice_is_matched_by_type_as_well_as_value() -> None:
    # ``True == 1`` in Python; the choice ``1`` is not the value ``True``.
    output = Output((OutputField("flag", "integer", choices=((1, "one"),)),))
    assert _table([{"flag": True}], output) == "flag\ntrue\n"
