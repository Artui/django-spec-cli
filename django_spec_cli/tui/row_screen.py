from __future__ import annotations

import json
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static


class RowScreen(Screen[None]):
    """One presented row as JSON, as the admin's object view shows it.

    Every key ``present`` gave it, hidden fields and ``affordances`` included."""

    BINDINGS = [Binding("escape", "back", "Back")]

    def __init__(self, row: Any, *, title: str) -> None:
        super().__init__()
        self.row = row
        self.sub_title = title

    def compose(self) -> ComposeResult:
        yield Header()
        shown = json.dumps(self.row, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2)
        with VerticalScroll():
            yield Static(Text(shown), id="row")
        yield Footer()

    def action_back(self) -> None:
        self.app.pop_screen()
