from __future__ import annotations

from typing import Any

import pytest
from asgiref.sync import sync_to_async
from django_service_specs import (
    DataclassPresenter,
    FilePresenter,
    Parameter,
    Parameters,
    SelectorKind,
    SelectorSpec,
    ServiceError,
    ServiceSpec,
    SpecRegistry,
    Unrestricted,
)
from textual.pilot import Pilot
from textual.widgets import Input, Select, Static, TextArea
from textual.worker import WorkerFailed

from django_spec_cli.tui.spec_form_screen import SpecFormScreen
from django_spec_cli.tui.spec_tui import SpecTui
from django_spec_cli.tui.specs_screen import SpecsScreen
from tests.commands_app.management.commands import notes
from tests.dispatch_app.models import Note
from tests.tui.utils import app_over

MARKUP = "[b]x[/b] [/x]"


def _refuse_with_markup() -> None:
    raise ServiceError(MARKUP)


def _nothing() -> None:
    return None


def _broken() -> None:
    raise RuntimeError("a bug, not a refusal")


def _export() -> bytes:
    raise AssertionError("a file spec is not run here")


note_spec = SelectorSpec(
    kind=SelectorKind.RETRIEVE,
    selector=lambda *, pk: Note.objects.filter(pk=pk),
    permissions=[Unrestricted()],
    reads=Parameters.of(Parameter("pk", "integer", required=True)),
    presenter=DataclassPresenter(notes.NoteOut),
)

registry = SpecRegistry()
for entry in notes.registry:
    registry.register(entry.name, entry.spec)
registry.register("note", note_spec)
registry.register("marked", ServiceSpec(service=_refuse_with_markup, permissions=[Unrestricted()]))
registry.register("nothing", ServiceSpec(service=_nothing, permissions=[Unrestricted()]))
registry.register("broken", ServiceSpec(service=_broken, permissions=[Unrestricted()]))
registry.register(
    "export",
    ServiceSpec(
        service=_export,
        permissions=[Unrestricted()],
        presenter=FilePresenter("application/pdf", filename="report.pdf"),
    ),
)


@pytest.fixture
def owner(django_user_model: Any) -> Any:
    return django_user_model.objects.create_user(username="ada")


@pytest.fixture
def note(owner: Any) -> Note:
    return Note.objects.create(owner=owner, title="Old")


async def _open(app: SpecTui, pilot: Pilot[None], subcommand: str) -> SpecFormScreen:
    app.on_specs_screen_chosen(SpecsScreen.Chosen(subcommand))
    await pilot.pause()
    assert isinstance(app.screen, SpecFormScreen)
    return app.screen


async def _fill(pilot: Pilot[None], screen: SpecFormScreen, **values: str) -> None:
    for name, value in values.items():
        screen.query_one(f"#field-{name}", Input).value = value
    await pilot.pause()


async def _run(pilot: Pilot[None], screen: SpecFormScreen) -> None:
    await pilot.press("ctrl+s")
    await screen.workers.wait_for_complete()
    await pilot.pause()


def _text(screen: SpecFormScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).content)


class TestOpening:
    async def test_choosing_a_spec_opens_its_form_and_esc_goes_back(self) -> None:
        app = app_over(registry)
        async with app.run_test() as pilot:
            await pilot.press("enter")
            assert isinstance(app.screen, SpecFormScreen)
            assert app.screen.subcommand == "rename-note"
            await pilot.press("escape")
            assert isinstance(app.screen, SpecsScreen)

    async def test_a_spec_source_opens_the_form_of_the_spec_it_compiles_to(self) -> None:
        app = app_over(registry)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "schedule")
            assert screen.query("#field-due_at")
            assert screen.writes


@pytest.mark.django_db(transaction=True)
class TestARead:
    async def test_it_runs_on_one_key_and_shows_the_row_as_the_command_s_table(
        self, owner: Any, note: Note
    ) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "note")
            await _fill(pilot, screen, pk=str(note.pk))
            await _run(pilot, screen)
            shown = _text(screen, "#result")
        assert "Old" in shown
        assert shown.splitlines()[0].split() == ["id", "title"]

    async def test_a_row_that_is_not_there_reads_not_found(self, owner: Any) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "note")
            await _fill(pilot, screen, pk="999")
            await _run(pilot, screen)
            assert _text(screen, "#result") == "Not found."


@pytest.mark.django_db(transaction=True)
class TestAWrite:
    async def test_one_ctrl_s_runs_nothing_and_asks_for_a_second(
        self, owner: Any, note: Note
    ) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "rename-note")
            await _fill(pilot, screen, pk=str(note.pk), title="New")
            await _run(pilot, screen)
            assert screen.armed
            assert "ctrl+s again runs it" in _text(screen, "#prompt")
            await sync_to_async(note.refresh_from_db)()
            assert note.title == "Old"
            await _run(pilot, screen)
            assert not screen.armed
            assert "New" in _text(screen, "#result")
        await sync_to_async(note.refresh_from_db)()
        assert note.title == "New"

    async def test_esc_disarms_the_write_without_leaving_the_form(
        self, owner: Any, note: Note
    ) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "rename-note")
            await _fill(pilot, screen, pk=str(note.pk), title="New")
            await _run(pilot, screen)
            await pilot.press("escape")
            assert app.screen is screen
            assert not screen.armed
            assert _text(screen, "#prompt") == ""
            await _run(pilot, screen)
        await sync_to_async(note.refresh_from_db)()
        assert note.title == "Old"

    async def test_an_edit_disarms_the_write(self, owner: Any, note: Note) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "rename-note")
            await _fill(pilot, screen, pk=str(note.pk), title="New")
            await _run(pilot, screen)
            await _fill(pilot, screen, title="Newer")
            assert not screen.armed
            await _run(pilot, screen)
        await sync_to_async(note.refresh_from_db)()
        assert note.title == "Old"

    @pytest.mark.parametrize(
        ("subcommand", "field", "value"),
        [
            ("schedule", "urgent", True),
            ("schedule", "tags", "red"),
            ("refuse", "kind", "other"),
        ],
    )
    async def test_an_edit_to_any_field_disarms_the_write(
        self, owner: Any, subcommand: str, field: str, value: Any
    ) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, subcommand)
            await _run(pilot, screen)
            assert screen.armed
            widget = screen.query_one(f"#field-{field}")
            setattr(widget, "text" if isinstance(widget, TextArea) else "value", value)
            await pilot.pause()
            assert not screen.armed

    async def test_a_result_of_none_reads_done(self, owner: Any) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "nothing")
            await _run(pilot, screen)
            await _run(pilot, screen)
            assert _text(screen, "#result") == "Done."


@pytest.mark.django_db(transaction=True)
class TestRefusals:
    async def test_a_value_coerce_flat_refuses_sits_beside_its_field_before_any_run(
        self, owner: Any
    ) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "schedule")
            await _fill(pilot, screen, due_at="2026-01-01T00:00:00Z", count="many")
            await _run(pilot, screen)
            assert not screen.armed
            assert _text(screen, "#refusal-count") == "Enter a whole number."
            assert _text(screen, "#result") == ""

    async def test_the_kernel_s_refusal_of_an_argument_sits_beside_its_field(
        self, owner: Any
    ) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "schedule")
            await _run(pilot, screen)
            await _run(pilot, screen)
            assert _text(screen, "#refusal-due_at") == "This field is required."
            assert _text(screen, "#refusal").startswith("Invalid")

    @pytest.mark.parametrize(
        ("kind", "shown"),
        [
            ("other", "The shelf is full."),
            ("unavailable", "The note is archived. (code: archived)"),
            ("validation_list", "Service validation error.\nFirst.\nSecond."),
        ],
    )
    async def test_any_other_refusal_reads_as_refusal_text_gives_it(
        self, owner: Any, kind: str, shown: str
    ) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "refuse")
            screen.query_one("#field-kind", Select).value = kind
            await pilot.pause()
            await _run(pilot, screen)
            await _run(pilot, screen)
            assert _text(screen, "#refusal") == shown

    async def test_a_refusal_carrying_markup_shows_as_typed(self, owner: Any) -> None:
        app = app_over(registry, owner)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "marked")
            await _run(pilot, screen)
            await _run(pilot, screen)
            assert _text(screen, "#refusal") == MARKUP

    async def test_an_error_that_is_no_refusal_is_raised_not_shown(self, owner: Any) -> None:
        app = app_over(registry, owner)
        with pytest.raises(WorkerFailed) as caught:
            async with app.run_test() as pilot:
                screen = await _open(app, pilot, "broken")
                await _run(pilot, screen)
                await _run(pilot, screen)
        assert isinstance(caught.value.error, RuntimeError)


class TestAFileSpec:
    async def test_it_names_its_subcommand_and_ctrl_s_runs_nothing(self) -> None:
        app = app_over(registry)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "export")
            assert not screen.query("ParameterFields")
            await _run(pilot, screen)
            assert _text(screen, "#file").endswith(
                "Run: manage.py notes export --as-user USER --output-file PATH"
            )
            assert not screen.armed
            assert _text(screen, "#result") == ""
