from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django_service_specs import UNSET

from django_spec_cli.argv.utils import option_string


@dataclass(frozen=True)
class ParameterDescriptor:
    """A [`Parameter`][django_service_specs.parameters.parameters.Parameter] seen from argv."""

    name: str
    type: str
    format: str | None = None
    items: str | None = None
    required: bool = False
    default: Any = UNSET
    choices: tuple[Any, ...] | None = None
    choice_labels: tuple[tuple[Any, str], ...] | None = None
    minimum: int | float | None = None
    maximum: int | float | None = None
    min_length: int | None = None
    max_length: int | None = None
    help: str | None = None
    argv: bool = True

    @property
    def option(self) -> str | None:
        """The option string, ``--due-at`` for ``due_at``, or ``None`` with no option."""
        return option_string(self.name) if self.argv else None
