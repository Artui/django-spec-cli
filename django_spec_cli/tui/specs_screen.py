from __future__ import annotations

from collections.abc import Mapping

from django_service_specs import RegisteredSpec, kernel_spec
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Footer, Header, OptionList
from textual.widgets.option_list import Option

from django_spec_cli.argv.utils import spec_summary


class SpecsScreen(Screen[None]):
    """Every spec the command serves, one line each, as the admin's index lists its models.

    A spec the kernel refuses as declared is greyed, with the reason, and cannot be chosen."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    class Chosen(Message):
        """``enter`` on the spec served as ``subcommand``."""

        def __init__(self, subcommand: str) -> None:
            super().__init__()
            self.subcommand = subcommand

    def __init__(self, entries: Mapping[str, RegisteredSpec], refusals: Mapping[str, str]) -> None:
        super().__init__()
        self._entries = entries
        self._refusals = refusals

    def compose(self) -> ComposeResult:
        yield Header()
        yield OptionList(*(self._option(name, entry) for name, entry in self._entries.items()))
        yield Footer()

    def _option(self, name: str, entry: RegisteredSpec) -> Option:
        # ``Text``, never ``str``: Textual reads markup in a string, and a docstring is no markup.
        prompt = Text.assemble(
            (name, "bold"), "  ", spec_summary(kernel_spec(entry.spec), entry.name)
        )
        refusal = self._refusals.get(entry.name)
        if refusal is None:
            return Option(prompt, id=name)
        prompt.append("\n" + refusal)
        return Option(prompt, id=name, disabled=True)

    def action_cursor_down(self) -> None:
        self.query_one(OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(OptionList).action_cursor_up()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.post_message(self.Chosen(str(event.option.id)))
