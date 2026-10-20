from __future__ import annotations

import io
from collections.abc import Callable, Iterator, Mapping
from typing import Any, TextIO

from django.db import models


class Status(models.TextChoices):
    """A choices enum, whose label a table cell shows in place of its stored value."""

    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"


def pulled_before_the_first_write(
    render: Callable[[Iterator[Mapping[str, Any]], TextIO], None],
) -> tuple[int, str]:
    """How many of three generated rows ``render`` read before its first write, and what it wrote.

    One means streamed: a renderer that turned the rows into a list, or looked
    ahead at the next one, would have read more.
    """
    pulled = 0
    at_first_write: list[int] = []

    def rows() -> Iterator[Mapping[str, Any]]:
        nonlocal pulled
        for n in range(3):
            pulled += 1
            yield {"id": n}

    class _Recording(io.StringIO):
        def write(self, text: str) -> int:
            if not at_first_write:
                at_first_write.append(pulled)
            return super().write(text)

    stream = _Recording()
    render(rows(), stream)
    return at_first_write[0], stream.getvalue()
