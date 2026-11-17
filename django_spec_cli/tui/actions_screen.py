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

    One the row does not afford, or this command cannot run, is greyed and cannot be chosen."""

    BINDINGS = [Binding("escape", "back", "Back")]

    def __init__(
        self,
        links: Mapping[str, Mapping[str, Any]],
        *,
        subcommands: Mapping[str, str],
        refusals: Mapping[str, str],
        title: str,
    ) -> None:
        super().__init__()
        self.links = dict(links)
        self._subcommands = dict(subcommands)
        self._refusals = dict(refusals)
        self._title = title

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(Text.assemble(("Actions", "bold"), "  ", self._title))
        yield OptionList(*(self._option(name, link) for name, link in self.links.items()))
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_back(self) -> None:
        self.dismiss(None)

    def _option(self, name: str, link: Mapping[str, Any]) -> Option:
        label = Text(name, "bold")
        target = link.get("name", "")
        if not link["available"]:
            # A row gone before its answers were asked is a bare ``{"available": False}``.
            why = f"{link['reason']} ({link['code']})" if "reason" in link else "unavailable"
            label.append(f"  {why}")
        elif target not in self._subcommands:
            label.append("  leads to an operation this command does not serve")
        elif target in self._refusals:
            label.append(f"  {self._refusals[target]}")
        else:
            label.append(f"  runs {self._subcommands[target]}")
            return Option(label, id=name)
        return Option(label, id=name, disabled=True)
