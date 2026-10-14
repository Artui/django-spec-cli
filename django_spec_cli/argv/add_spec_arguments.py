"""``add_spec_arguments`` - one argparse option per parameter a command line can send."""

from __future__ import annotations

import argparse
import json
from collections.abc import Collection
from typing import Any

from django.core.exceptions import ImproperlyConfigured

from django_service_specs.commands.argv.describe_parameters import describe_parameters
from django_service_specs.commands.argv.parameter_descriptor import ParameterDescriptor
from django_service_specs.commands.argv.utils import destination, option_string
from django_service_specs.parameters.parameters import Parameters
from django_service_specs.types.unset import UNSET


def add_spec_arguments(
    parser: argparse.ArgumentParser, parameters: Parameters, *, reserved: Collection[str] = ()
) -> None:
    """Add an option to ``parser`` for each parameter a command line can send.

    The option is ``--`` and the name with ``_`` as ``-``: ``due_at`` is
    ``--due-at``. Argparse only collects strings here, and every decision about
    them is the kernel's, so a command line refuses what an HTTP caller would
    be refused, in the same words:

    - **No value is converted.** No option sets ``type=``; every value stays
      the string typed, and [`coerce_flat`][django_service_specs.parameters.coerce_flat.coerce_flat]
      reads it as it reads a query string.
    - **No option is required by argparse.** The shape check owns "missing",
      so a required parameter is refused as HTTP refuses it, beside every other
      mistake in the call, and ``--help`` marks it ``(required)``.
    - **No choice is enforced by argparse.** The choices are listed in
      ``--help`` and the shape check refuses any other value. Argparse's own
      ``choices=`` would answer one mistake with a second message and exit
      code, and only for a parameter whose choices are all strings.
    - **An omitted option is absent from the namespace**, never ``None``: its
      default is ``argparse.SUPPRESS``. That keeps it apart from an empty
      string and from ``--no-flag``.
    - A ``boolean`` is a ``--flag``/``--no-flag`` pair, and an ``array`` is a
      repeated option, ``--ids 1 --ids 2``, each value one element.
    - Each value lands under a namespaced destination rather than the
      parameter's name, so a parameter named ``verbosity`` or ``settings``
      cannot overwrite ``BaseCommand``'s own. Read the namespace back with
      [`parsed_arguments`][django_service_specs.commands.argv.parsed_arguments.parsed_arguments].

    A parameter with no honest flat spelling - an object, an array of objects,
    a file - gets no option: see
    [`ParameterDescriptor`][django_service_specs.commands.argv.parameter_descriptor.ParameterDescriptor].

    ``reserved`` is the option strings the command owns itself, such as
    ``--as-user`` and Django's ``--verbosity``; ``--help`` is always reserved,
    since every parser owns its own.

    Raises:
        ImproperlyConfigured: naming the parameter and the option, when an
            option would be one in ``reserved``, or one another parameter maps
            to as well - ``a_b`` and ``a-b``, or a boolean ``x``, whose
            ``--no-x`` is a parameter ``no_x``'s option. Every option is
            checked before the first is added, so a refused spec leaves the
            parser as it was.
    """
    descriptors = [d for d in describe_parameters(parameters) if d.argv]
    _check_options(descriptors, frozenset(reserved) | {"--help"})
    for descriptor in descriptors:
        _add_option(parser, descriptor)


def _option_strings(descriptor: ParameterDescriptor) -> list[str]:
    """Every option string a parameter claims: a boolean claims its negative too."""
    option = option_string(descriptor.name)
    if descriptor.type == "boolean":
        return [option, "--no-" + option[2:]]
    return [option]


def _check_options(descriptors: list[ParameterDescriptor], reserved: frozenset[str]) -> None:
    claimed: dict[str, str] = {}
    for descriptor in descriptors:
        for option in _option_strings(descriptor):
            if option in reserved:
                raise ImproperlyConfigured(
                    f"Parameter {descriptor.name!r}: the option {option!r} is the command's "
                    "own; rename the parameter."
                )
            if option in claimed:
                raise ImproperlyConfigured(
                    f"Parameters {claimed[option]!r} and {descriptor.name!r} both map to the "
                    f"option {option!r}; rename one of them."
                )
            claimed[option] = descriptor.name


def _add_option(parser: argparse.ArgumentParser, descriptor: ParameterDescriptor) -> None:
    common: dict[str, Any] = {
        "dest": destination(descriptor.name),
        "default": argparse.SUPPRESS,
        "help": _help(descriptor),
    }
    if descriptor.type == "boolean":
        # No ``metavar``, ``type`` or ``choices``: a flag takes no value, and
        # Python 3.12 deprecates passing them to this action.
        parser.add_argument(
            option_string(descriptor.name), action=argparse.BooleanOptionalAction, **common
        )
        return
    parser.add_argument(
        option_string(descriptor.name),
        action="append" if descriptor.type == "array" else "store",
        # Set, or argparse prints the namespaced destination in its place.
        metavar=_metavar(descriptor),
        **common,
    )


def _metavar(descriptor: ParameterDescriptor) -> str:
    """What one value is: an array's is its element's, and a format names a string's."""
    if descriptor.format is not None:
        return descriptor.format.upper()
    kind = descriptor.items if descriptor.type == "array" else descriptor.type
    # An ``any``, and an array declaring no element, take any value.
    return "VALUE" if kind in (None, "any") else kind.upper()


def _help(descriptor: ParameterDescriptor) -> str | None:
    notes: list[str] = []
    if descriptor.type == "array":
        notes.append("repeat the option for each element")
    if descriptor.choices is not None:
        pairs = descriptor.choice_labels or ()
        notes.append("one of: " + ", ".join(_choice(c, pairs) for c in descriptor.choices))
    for label, bound in (("minimum", descriptor.minimum), ("maximum", descriptor.maximum)):
        if bound is not None:
            notes.append(f"{label} {bound}")
    for label, length in (("at least", descriptor.min_length), ("at most", descriptor.max_length)):
        if length is not None:
            notes.append(f"{label} {length}")
    if descriptor.required:
        notes.append("required")
    if descriptor.default is not UNSET:
        notes.append(f"default: {_text(descriptor.default)}")
    # ``str``: a help text may be a lazy translation, rendered here.
    parts = [str(descriptor.help)] if descriptor.help else []
    if notes:
        parts.append("(" + "; ".join(notes) + ")")
    # Argparse %-formats every help string, so a literal ``%`` - in the
    # declared help, a choice, a label or a default - is doubled to print as
    # written: test_a_percent_sign_in_any_help_text_is_printed_as_written.
    return " ".join(parts).replace("%", "%%") if parts else None


def _choice(choice: Any, pairs: tuple[tuple[Any, str], ...]) -> str:
    """A choice as typed, with its label where one is declared."""
    # Matched by type as well as value, as the declaration keeps them apart:
    # ``1`` and ``True`` are equal to Python and two choices to a caller. Each
    # condition is held by its own case of test_a_choice_is_shown_with_its_own_label:
    # [equal-across-types] (the type) and [unlabelled] (the value).
    label = next((lb for v, lb in pairs if type(v) is type(choice) and v == choice), None)
    return _text(choice) if label is None else f"{_text(choice)} ({label})"


def _text(value: Any) -> str:
    """A value as it is typed: a string bare, anything else as its JSON.

    An empty string is quoted, since bare it would read as no value at all.
    """
    # Each condition is held by its own test: test_an_empty_string_default_is_shown_quoted
    # (the emptiness) and test_a_choice_that_is_not_a_string_is_listed_as_json (the type).
    return value if isinstance(value, str) and value else json.dumps(value)
