from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal

from textual.widgets import Static

from django_spec_cli.tui.row_screen import RowScreen
from tests.commands_app.management.commands import notes
from tests.tui.utils import app_over

MARKUP = "[b]x[/b] [/x]"


async def test_the_row_shows_as_indented_json_with_markup_as_typed() -> None:
    row = {"title": MARKUP, "price": Decimal("9.99"), "due": dt.date(2026, 1, 2)}
    app = app_over(notes.registry)
    async with app.run_test() as pilot:
        app.push_screen(RowScreen(row, title="books"))
        await pilot.pause()
        shown = str(app.screen.query_one("#row", Static).content)
        assert app.screen.sub_title == "books"
    assert json.loads(shown) == {"title": MARKUP, "price": "9.99", "due": "2026-01-02"}
    assert shown.startswith('{\n  "title": ')
