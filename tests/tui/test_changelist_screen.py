from __future__ import annotations

import io
import json
from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace
from typing import Annotated, Any

import pytest
from django.contrib.auth.models import AnonymousUser
from django_service_specs import (
    DataclassPresenter,
    FieldMarking,
    Parameter,
    Parameters,
    SelectorKind,
    SelectorSpec,
    ServiceError,
    SpecRegistry,
    Unrestricted,
)
from textual.pilot import Pilot
from textual.widgets import DataTable, Input, Static
from textual.worker import WorkerFailed

from django_spec_cli.render.render_table import render_table
from django_spec_cli.tui.changelist_screen import ChangelistScreen
from django_spec_cli.tui.row_screen import RowScreen
from django_spec_cli.tui.specs_screen import SpecsScreen
from tests.commands_app.management.commands import notes
from tests.dispatch_app.models import Note
from tests.render.utils import Status
from tests.tui.utils import app_over

MARKUP = "[b]x[/b] [/x]"


@dataclass
class Book:
    id: Annotated[int, FieldMarking.handle()]
    title: str
    status: Status
    price: Decimal
    tags: list[str]
    etag: Annotated[str, FieldMarking.hidden()]


BOOKS = [
    SimpleNamespace(
        id=1, title="Dune", status=Status.PUBLISHED, price=Decimal("9.99"), tags=["sf"], etag="a"
    ),
    SimpleNamespace(
        id=22, title="Emma", status=Status.DRAFT, price=Decimal("12.50"), tags=[], etag="b"
    ),
]


@dataclass
class NoteRow:
    id: Annotated[int, FieldMarking.handle()]
    title: str
    owner_id: Annotated[int, FieldMarking.hidden()]


def notes_of(*, user: Any, search: str = "", min_id: int = 0) -> Any:
    if search == "boom":
        raise ServiceError(MARKUP)
    return Note.objects.filter(owner=user, title__icontains=search, pk__gte=min_id)


def _broken() -> list[Any]:
    raise RuntimeError("a bug, not a refusal")


registry = SpecRegistry()
registry.register(
    "books",
    SelectorSpec(
        kind=SelectorKind.LIST,
        selector=lambda: BOOKS,
        permissions=[Unrestricted()],
        presenter=DataclassPresenter(Book),
    ),
)
registry.register(
    "marked",
    SelectorSpec(
        kind=SelectorKind.LIST,
        selector=lambda: [{MARKUP: MARKUP}],
        permissions=[Unrestricted()],
    ),
)
registry.register(
    "my_notes",
    SelectorSpec(
        kind=SelectorKind.LIST,
        selector=notes_of,
        permissions=[notes.IsSignedIn()],
        reads=Parameters.of(Parameter("search", "string"), Parameter("min_id", "integer")),
        presenter=DataclassPresenter(NoteRow),
        affordances={"rename": notes.rename_note_spec},
    ),
)
registry.register(
    "broken",
    SelectorSpec(kind=SelectorKind.LIST, selector=_broken, permissions=[Unrestricted()]),
)


@pytest.fixture
def owner(django_user_model: Any) -> Any:
    owner = django_user_model.objects.create_user(username="ada")
    for n in range(5):
        Note.objects.create(owner=owner, title=f"Note {n}")
    return owner


@pytest.fixture
def pages_of_two(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ChangelistScreen, "page_size", 2)


async def _open(app: Any, pilot: Pilot[None], subcommand: str) -> ChangelistScreen:
    app.on_specs_screen_chosen(SpecsScreen.Chosen(subcommand))
    await pilot.pause()
    assert isinstance(app.screen, ChangelistScreen)
    await _settle(pilot, app.screen)
    return app.screen


async def _settle(pilot: Pilot[None], screen: ChangelistScreen) -> None:
    await screen.workers.wait_for_complete()
    await pilot.pause()


async def _press(pilot: Pilot[None], screen: ChangelistScreen, *keys: str) -> None:
    for key in keys:
        await pilot.press(key)
        await _settle(pilot, screen)


def _cells(screen: ChangelistScreen) -> list[list[str]]:
    table = screen.query_one(DataTable)
    return [[cell.plain for cell in table.get_row_at(n)] for n in range(table.row_count)]


def _headers(screen: ChangelistScreen) -> list[str]:
    return [column.label.plain for column in screen.query_one(DataTable).ordered_columns]


def _text(screen: Any, selector: str) -> str:
    return str(screen.query_one(selector, Static).content)


async def _first_pk(owner: Any) -> int:
    first = await Note.objects.filter(owner=owner).afirst()
    assert first is not None
    return first.pk


def _titles(screen: ChangelistScreen) -> list[str]:
    return [row["title"] for row in screen.rows]


class TestTheTable:
    async def test_columns_and_cells_are_render_table_s_for_the_same_rows(self) -> None:
        app = app_over(registry)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "books")
            shown = [_headers(screen), *_cells(screen)]
            rows = screen.rows
            output = screen.spec.output()
        printed = io.StringIO()
        render_table(rows, output, printed)
        assert shown == [line.split() for line in printed.getvalue().splitlines()]
        assert shown[1] == ["1", "Dune", "Published", "9.99", '["sf"]']
        assert "etag" in rows[0]

    async def test_a_number_column_is_right_aligned(self) -> None:
        app = app_over(registry)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "books")
            row = screen.query_one(DataTable).get_row_at(0)
        assert [cell.justify for cell in row] == ["right", "left", "left", "left", "left"]

    async def test_markup_in_a_header_or_a_cell_shows_as_typed(self) -> None:
        app = app_over(registry)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "marked")
            assert _headers(screen) == [MARKUP]
            assert _cells(screen) == [[MARKUP]]

    async def test_a_bug_in_the_selector_is_raised_not_shown(self) -> None:
        app = app_over(registry)
        with pytest.raises(WorkerFailed) as caught:
            async with app.run_test() as pilot:
                app.on_specs_screen_chosen(SpecsScreen.Chosen("broken"))
                await pilot.pause()
                await _settle(pilot, app.screen)
        assert isinstance(caught.value.error, RuntimeError)


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("pages_of_two")
class TestPaging:
    async def test_it_opens_on_page_one_and_reports_pages_and_total(self, owner: Any) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "my-notes")
            assert _titles(screen) == ["Note 0", "Note 1"]
            assert _text(screen, "#status") == "Page 1 of 3, 5 in all"

    async def test_n_and_p_turn_the_page(self, owner: Any) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "my-notes")
            await _press(pilot, screen, "n")
            assert _titles(screen) == ["Note 2", "Note 3"]
            await _press(pilot, screen, "p")
            assert _titles(screen) == ["Note 0", "Note 1"]

    async def test_past_the_last_page_it_stays_on_the_last_and_says_so(self, owner: Any) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "my-notes")
            await _press(pilot, screen, "n", "n", "n")
            assert screen.page == 3
            assert _titles(screen) == ["Note 4"]
            assert _text(screen, "#status") == "Page 3 of 3, 5 in all"
            await _press(pilot, screen, "p")
            assert _titles(screen) == ["Note 2", "Note 3"]

    async def test_before_the_first_page_it_stays_on_the_first(self, owner: Any) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "my-notes")
            await _press(pilot, screen, "p")
            assert screen.page == 1
            await _press(pilot, screen, "n")
            assert _titles(screen) == ["Note 2", "Note 3"]

    async def test_r_reloads_the_page_shown(self, owner: Any) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "my-notes")
            await _press(pilot, screen, "n")
            await Note.objects.filter(title="Note 2").aupdate(title="Renamed")
            await _press(pilot, screen, "r")
            assert _titles(screen) == ["Renamed", "Note 3"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("pages_of_two")
class TestTheFilterBar:
    async def test_enter_in_a_field_re_dispatches_with_the_entered_reads(self, owner: Any) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "my-notes")
            await _press(pilot, screen, "n")
            screen.query_one("#field-search", Input).value = "4"
            screen.query_one("#field-search", Input).focus()
            await _press(pilot, screen, "enter")
            assert _titles(screen) == ["Note 4"]
            assert _text(screen, "#status") == "Page 1 of 1, 1 in all"
            assert screen.arguments == {"search": "4"}

    async def test_ctrl_s_applies_it_from_any_field(self, owner: Any) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "my-notes")
            first = await _first_pk(owner)
            screen.query_one("#field-min_id", Input).value = str(first + 3)
            await _press(pilot, screen, "ctrl+s")
            assert _titles(screen) == ["Note 3", "Note 4"]

    async def test_slash_focuses_the_bar_and_a_typed_n_is_text_not_a_page(self, owner: Any) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "my-notes")
            await _press(pilot, screen, "slash", "n")
            assert screen.query_one("#field-search", Input).value == "n"
            assert screen.page == 1

    async def test_a_dispatch_refusal_keeps_the_rows_and_the_filter_they_came_from(
        self, owner: Any
    ) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "my-notes")
            screen.query_one("#field-search", Input).value = "boom"
            await _press(pilot, screen, "ctrl+s")
            assert _text(screen, "#refusal") == MARKUP
            assert _titles(screen) == ["Note 0", "Note 1"]
            assert screen.arguments == {}
            screen.query_one(DataTable).focus()
            await _press(pilot, screen, "n")
            assert _titles(screen) == ["Note 2", "Note 3"]
            assert _text(screen, "#refusal") == ""

    async def test_a_value_coerce_flat_refuses_sits_beside_its_field_and_nothing_runs(
        self, owner: Any
    ) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "my-notes")
            screen.query_one("#field-min_id", Input).value = "abc"
            await _press(pilot, screen, "ctrl+s")
            assert _text(screen, "#refusal-min_id") != ""
            assert _titles(screen) == ["Note 0", "Note 1"]
            screen.query_one("#field-min_id", Input).value = ""
            await _press(pilot, screen, "ctrl+s")
            assert _text(screen, "#refusal-min_id") == ""

    async def test_a_refusal_on_opening_leaves_an_empty_table_and_says_why(self) -> None:
        app = app_over(registry, AnonymousUser())
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "my-notes")
            assert _text(screen, "#refusal") != ""
            assert screen.query_one(DataTable).row_count == 0

    async def test_slash_without_reads_leaves_the_table_focused(self) -> None:
        app = app_over(registry)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "books")
            await _press(pilot, screen, "slash")
            assert screen.focused is screen.query_one(DataTable)


@pytest.mark.django_db(transaction=True)
class TestKeys:
    async def test_enter_opens_the_presented_row_with_hidden_fields_and_affordances(
        self, owner: Any
    ) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "my-notes")
            await _press(pilot, screen, "down", "enter")
            assert isinstance(app.screen, RowScreen)
            shown = json.loads(_text(app.screen, "#row"))
            assert shown == screen.rows[1]
            assert shown["owner_id"] == owner.pk
            assert shown["affordances"] == {"rename": {"available": True}}
            assert "owner_id" not in _headers(screen)
            await pilot.press("escape")
            assert app.screen is screen

    async def test_esc_leaves_the_filter_bar_then_the_screen(self, owner: Any) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "my-notes")
            await _press(pilot, screen, "slash", "escape")
            assert app.screen is screen
            assert screen.focused is screen.query_one(DataTable)
            await pilot.press("escape")
            assert isinstance(app.screen, SpecsScreen)
