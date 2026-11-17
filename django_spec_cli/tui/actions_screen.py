from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option


class ActionsScreen(Screen[str | None]):
    """A row's actions as ``row_links`` answers them, as the admin's actions menu lists them.

    One the row does not afford, or this command does not serve, is greyed and cannot be chosen."""

    BINDINGS = [Binding("escape", "back", "Back")]

    def __init__(
        self,
        links: Mapping[str, Mapping[str, Any]],
        *,
        subcommands: Mapping[str, str],
        title: str,
    ) -> None:
        super().__init__()
        self.links = dict(links)
        self._subcommands = dict(subcommands)
        self._title = title

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(Text.assemble(("Actions", "bold"), "  ", self._title))
        options = (_option(name, link, self._subcommands) for name, link in self.links.items())
        yield OptionList(*options)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_back(self) -> None:
        self.dismiss(None)


def _option(name: str, link: Mapping[str, Any], subcommands: Mapping[str, str]) -> Option:
    label = Text(name, "bold")
    if not link["available"]:
        label.append(f"  {link['reason']} ({link['code']})")
        return Option(label, id=name, disabled=True)
    subcommand = subcommands.get(link.get("name", ""))
    if subcommand is None:
        label.append("  leads to an operation this command does not serve")
        return Option(label, id=name, disabled=True)
    label.append(f"  runs {subcommand}")
    return Option(label, id=name)
