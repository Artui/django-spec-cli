from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated

import django
from django.conf import settings

settings.configure(
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
)
django.setup()

from django_service_specs import (  # noqa: E402
    DEFAULT_POOL_SEEDS,
    DataclassPresenter,
    DataclassValidator,
    FieldMarking,
    Parameter,
    Parameters,
    SelectorKind,
    SelectorSpec,
    ServiceSpec,
    SpecRegistry,
    Unrestricted,
)
from textual.widgets import Input  # noqa: E402

from django_spec_cli.tui.spec_tui import SpecTui  # noqa: E402


@dataclass
class Book:
    id: Annotated[int, FieldMarking.handle()]
    title: str
    price: Decimal


BOOKS = [
    SimpleNamespace(id=1, title="Dune", price=Decimal("9.99")),
    SimpleNamespace(id=2, title="Emma", price=Decimal("12.50")),
    SimpleNamespace(id=3, title="Kim", price=Decimal("7.25")),
]


def books_of(*, search: str = "") -> list[SimpleNamespace]:
    return [book for book in BOOKS if search.lower() in book.title.lower()]


@dataclass
class Retitle:
    book: int
    title: str


def retitle(*, book: int, title: str) -> str:
    return title


registry = SpecRegistry()
registry.register(
    "list_books",
    SelectorSpec(
        kind=SelectorKind.LIST,
        selector=books_of,
        permissions=[Unrestricted()],
        reads=Parameters.of(Parameter("search", "string", help="Part of the title.")),
        presenter=DataclassPresenter(Book),
    ),
)
registry.register(
    "retitle_book",
    ServiceSpec(
        service=retitle,
        permissions=[Unrestricted()],
        validator=DataclassValidator(Retitle),
    ),
)


def _app() -> SpecTui:
    entries = {entry.name.replace("_", "-"): entry for entry in registry}
    return SpecTui(
        entries=entries,
        refusals={},
        principal=SimpleNamespace(is_authenticated=True),
        pool_seeds=DEFAULT_POOL_SEEDS,
        command_label="library",
    )


async def _shoot(out: Path) -> None:
    app = _app()
    async with app.run_test(size=(100, 22)) as pilot:
        await pilot.pause()
        app.save_screenshot("tui-specs.svg", str(out))
        await pilot.press("enter")
        await pilot.pause()
        await app.screen.workers.wait_for_complete()
        await pilot.pause()
        app.save_screenshot("tui-changelist.svg", str(out))
        await pilot.press("escape", "down", "enter")
        await pilot.pause()
        app.screen.query_one(Input).focus()
        await pilot.press("1", "tab", *"Emma, revised", "ctrl+s")
        await pilot.pause()
        app.save_screenshot("tui-form.svg", str(out))


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/img")
    target.mkdir(parents=True, exist_ok=True)
    asyncio.run(_shoot(target))
