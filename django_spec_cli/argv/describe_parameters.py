from __future__ import annotations

import json
from typing import Any

from django_service_specs import UNSET, Parameter, Parameters

from django_spec_cli.argv.parameter_descriptor import ParameterDescriptor

_FLAT_TYPES = ("string", "integer", "number", "boolean", "any")
"""The types one string on a command line spells: ``coerce_flat`` reads it as one
of these, and an ``any`` is handed on as the string it is."""

_FLAT_ELEMENTS = (None, "string", "integer", "number", "boolean")
"""An array's elements a repeated option spells: a declared scalar, or no
declared ``items``, whose elements stay the strings given."""


def describe_parameters(parameters: Parameters) -> tuple[ParameterDescriptor, ...]:
    """One [`ParameterDescriptor`][django_spec_cli.argv.parameter_descriptor.ParameterDescriptor] per parameter, in declaration order.

    Never refuses a declaration: a parameter with no flat spelling is
    described with ``argv=False`` rather than left out, so a command can still
    say in ``--help`` that a spec takes something argv cannot send.
    """  # noqa: E501
    return tuple(_describe(param) for param in parameters)


def _describe(param: Parameter) -> ParameterDescriptor:
    return ParameterDescriptor(
        name=param.name,
        type=param.type,
        format=param.format,
        items=param.items if isinstance(param.items, str) else None,
        # The shape check's rule for an omitted argument: "(required)" marks a refused omission.
        required=param.required and param.default is UNSET,
        default=_shown_default(param.default),
        choices=param.choices,
        choice_labels=param.choice_labels,
        minimum=param.minimum,
        maximum=param.maximum,
        min_length=param.min_length,
        max_length=param.max_length,
        help=param.help,
        argv=_has_flat_spelling(param),
    )


def _has_flat_spelling(param: Parameter) -> bool:
    # Read from the type: ``nested`` is narrower than "no honest option".
    if param.type == "array":
        return param.items in _FLAT_ELEMENTS
    return param.type in _FLAT_TYPES


def _shown_default(default: Any) -> Any:
    """The default, where JSON spells it; otherwise ``UNSET``, so nothing is shown."""
    try:
        json.dumps(default, allow_nan=False)
    except (TypeError, ValueError):
        return UNSET
    return default
