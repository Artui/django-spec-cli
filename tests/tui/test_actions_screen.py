from __future__ import annotations

from typing import Any

from django_service_specs import SpecRegistry
from rich.text import Text
from textual.pilot import Pilot
from textual.widgets import OptionList

from django_spec_cli.tui.actions_screen import ActionsScreen
from tests.tui.utils import app_over

MARKUP = "[b]x[/b] [/x]"

LINKS: dict[str, dict[str, Any]] = {
    "rename": {"available": True, "spec": None, "arguments": {"pk": 1}, "name": "rename_note"},
    "archive": {
        "available": False,
        "code": "archived",
        "reason": "An archived note stays archived.",
        "spec": None,
        "arguments": {"pk": 1},
        "name": "archive_note",
    },
    "export": {"available": True, "spec": None, "arguments": {}},
}
SUBCOMMANDS = {"rename_note": "rename-note", "archive_note": "archive-note"}


async def _open(
    pilot: Pilot[None], links: dict[str, dict[str, Any]], chosen: list[str | None]
) -> ActionsScreen:
    screen = ActionsScreen(links, subcommands=SUBCOMMANDS, title="notes")
    pilot.app.push_screen(screen, chosen.append)
    await pilot.pause()
    return screen


def _labels(screen: ActionsScreen) -> list[tuple[str, bool]]:
    options = screen.query_one(OptionList)
    found = []
    for n in range(options.option_count):
        option = options.get_option_at_index(n)
        assert isinstance(option.prompt, Text)
        found.append((option.prompt.plain, option.disabled))
    return found


class TestTheList:
    async def test_each_action_names_what_it_runs_or_why_it_cannot(self) -> None:
        async with app_over(SpecRegistry()).run_test() as pilot:
            screen = await _open(pilot, LINKS, [])
            assert _labels(screen) == [
                ("rename  runs rename-note", False),
                ("archive  An archived note stays archived. (archived)", True),
                ("export  leads to an operation this command does not serve", True),
            ]

    async def test_markup_in_a_name_or_a_reason_shows_as_typed(self) -> None:
        links = {MARKUP: {**LINKS["archive"], "reason": MARKUP, "code": MARKUP}}
        async with app_over(SpecRegistry()).run_test() as pilot:
            screen = await _open(pilot, links, [])
            assert _labels(screen) == [(f"{MARKUP}  {MARKUP} ({MARKUP})", True)]


class TestChoosing:
    async def test_enter_on_an_available_action_hands_back_its_name(self) -> None:
        chosen: list[str | None] = []
        async with app_over(SpecRegistry()).run_test() as pilot:
            await _open(pilot, LINKS, chosen)
            await pilot.press("enter")
            await pilot.pause()
        assert chosen == ["rename"]

    async def test_a_greyed_action_cannot_be_reached_or_chosen(self) -> None:
        chosen: list[str | None] = []
        async with app_over(SpecRegistry()).run_test() as pilot:
            screen = await _open(pilot, LINKS, chosen)
            await pilot.press("down", "down", "end")
            await pilot.pause()
            assert screen.query_one(OptionList).highlighted == 0
            await pilot.press("enter")
            await pilot.pause()
        assert chosen == ["rename"]

    async def test_with_none_available_nothing_can_be_chosen(self) -> None:
        chosen: list[str | None] = []
        links = {"archive": LINKS["archive"], "export": LINKS["export"]}
        async with app_over(SpecRegistry()).run_test() as pilot:
            screen = await _open(pilot, links, chosen)
            await pilot.press("down", "enter")
            await pilot.pause()
            assert pilot.app.screen is screen
        assert chosen == []

    async def test_esc_hands_back_nothing(self) -> None:
        chosen: list[str | None] = []
        async with app_over(SpecRegistry()).run_test() as pilot:
            await _open(pilot, LINKS, chosen)
            await pilot.press("escape")
            await pilot.pause()
        assert chosen == [None]
