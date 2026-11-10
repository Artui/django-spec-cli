from __future__ import annotations

import argparse
import json
from collections.abc import Collection
from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django_service_specs import UNSET, Parameters

from django_spec_cli.argv.describe_parameters import describe_parameters
from django_spec_cli.argv.parameter_descriptor import ParameterDescriptor
from django_spec_cli.argv.utils import destination, option_string


def add_spec_arguments(
    parser: argparse.ArgumentParser, parameters: Parameters, *, reserved: Collection[str] = ()
) -> None:
    """Add an option to ``parser`` for each parameter a command line can send."""
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
    option = option_string(descriptor.name)
    common: dict[str, Any] = {
        "dest": destination(descriptor.name),
        "default": argparse.SUPPRESS,
        "help": _help(descriptor),
    }
    if descriptor.type == "boolean":
        parser.add_argument(option, action=argparse.BooleanOptionalAction, **common)
        return
    parser.add_argument(
        option,
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
    parts = [str(descriptor.help)] if descriptor.help else []
    if notes:
        parts.append("(" + "; ".join(notes) + ")")
    # Argparse %-formats help, so a literal ``%`` is doubled to print as written.
    return " ".join(parts).replace("%", "%%") if parts else None


def _choice(choice: Any, pairs: tuple[tuple[Any, str], ...]) -> str:
    """A choice as typed, with its label where one is declared."""
    label = next((lb for v, lb in pairs if type(v) is type(choice) and v == choice), None)
    return _text(choice) if label is None else f"{_text(choice)} ({label})"


def _text(value: Any) -> str:
    """A value as it is typed: a string bare unless empty, anything else as its JSON."""
    return value if isinstance(value, str) and value else json.dumps(value)
