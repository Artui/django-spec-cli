"""``ParameterDescriptor`` - one parameter, as a command line sees it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django_service_specs.commands.argv.utils import option_string
from django_service_specs.types.unset import UNSET


@dataclass(frozen=True)
class ParameterDescriptor:
    """A [`Parameter`][django_service_specs.parameters.parameters.Parameter] seen from argv.

    What a command line can say about a parameter, built by
    [`describe_parameters`][django_service_specs.commands.argv.describe_parameters.describe_parameters]:
    the option it is sent with, and what ``--help`` can honestly show about
    the value. Each field is the declaration's, read for a person typing it,
    and three are narrower than the ``Parameter`` they come from:

    - ``required`` is whether **an omitted option is refused**: a parameter
      declared required with a default is not, since the shape check lets the
      Validator supply the default. A spec declared ``partial`` refuses no
      omission at all, which the declaration cannot see; the command that
      knows its spec says so.
    - ``default`` is the declared default **only where JSON can spell it**:
      ``None`` included, and never a callable, a sentinel or NaN, whose
      ``repr`` in the help would be a concrete falsehood. ``UNSET`` means
      nothing is shown, not that nothing is declared.
    - ``items`` is an array's element type, or ``None``: an element that is a
      row of nested Parameters is no type a command line could show.

    ``argv`` is ``False`` for a parameter that has no honest flat spelling -
    an object, an array of objects, of arrays or of files, and a file - so
    no option is invented for it: a dotted option for a nested field would be
    a syntax only this command spoke. Sent anyway, under its name by a
    caller that fills the arguments itself, it still reaches ``coerce_flat``'s
    refusal; left out, the shape check's ``required``.
    """

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
