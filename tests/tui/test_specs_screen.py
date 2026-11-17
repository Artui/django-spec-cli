from __future__ import annotations

from typing import Any

from django_service_specs import ServiceSpec, Unrestricted
from textual.widgets import OptionList

from django_spec_cli.tui.specs_screen import SpecsScreen
from tests.commands_app.management.commands import notes
from tests.test_spec_command import registry_of
from tests.tui.utils import app_over


def _lines(options: OptionList) -> list[tuple[str, str, bool]]:
    return [(str(option.id), str(option.prompt), option.disabled) for option in options.options]


async def test_every_entry_is_listed_with_its_summary_and_kind() -> None:
    app = app_over(notes.registry)
    async with app.run_test():
        lines = _lines(app.screen.query_one(OptionList))
    assert [name for name, _, _ in lines] == [
        "rename-note",
        "list-notes",
        "schedule",
        "refuse",
        "retitle",
        "ping",
        "my-notes",
    ]
    assert lines[0] == ("rename-note", "rename-note  Give a note a new title. (write)", False)
    assert lines[1] == ("list-notes", "list-notes  list_notes (read)", False)


async def test_a_spec_refused_as_declared_is_greyed_with_its_reason_and_cannot_be_chosen() -> None:
    chosen: list[str] = []
    app = app_over(notes.registry, refusals={"rename_note": "'rename_note' cannot run."})
    app.notify = lambda message, **_: chosen.append(message)
    async with app.run_test() as pilot:
        options = app.screen.query_one(OptionList)
        assert _lines(options)[0] == (
            "rename-note",
            "rename-note  Give a note a new title. (write)\n'rename_note' cannot run.",
            True,
        )
        assert options.get_option_at_index(0).disabled
        await pilot.press("enter")
    # The cursor starts on the first spec that can be chosen.
    assert chosen == ["list-notes has no screen yet."]


async def test_j_and_k_move_the_cursor() -> None:
    chosen: list[str] = []
    app = app_over(notes.registry)
    app.notify = lambda message, **_: chosen.append(message)
    async with app.run_test() as pilot:
        await pilot.press("j", "j", "k", "enter")
    assert chosen == ["list-notes has no screen yet."]


async def test_markup_in_a_docstring_is_shown_as_typed() -> None:
    def tagged() -> Any:
        """Bold [b]x[/b] and a stray [/x]."""

    registry = registry_of(tagged=ServiceSpec(service=tagged, permissions=[Unrestricted()]))
    app = app_over(registry)
    async with app.run_test():
        assert isinstance(app.screen, SpecsScreen)
        [(_, prompt, _)] = _lines(app.screen.query_one(OptionList))
    assert prompt == "tagged  Bold [b]x[/b] and a stray [/x]. (write)"
