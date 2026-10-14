"""``describe_parameters`` - a spec's Parameters, as a command line sees them."""

from __future__ import annotations

import json
from typing import Any

from django_service_specs.commands.argv.parameter_descriptor import ParameterDescriptor
from django_service_specs.parameters.parameters import Parameter, Parameters
from django_service_specs.types.unset import UNSET

_FLAT_TYPES = ("string", "integer", "number", "boolean", "any")
"""The types one string on a command line spells: ``coerce_flat`` reads it as one
of these, and an ``any`` is handed on as the string it is."""

_FLAT_ELEMENTS = (None, "string", "integer", "number", "boolean")
"""An array's elements a repeated option spells: a declared scalar, or no
declared ``items``, whose elements stay the strings given."""


def describe_parameters(parameters: Parameters) -> tuple[ParameterDescriptor, ...]:
    """One [`ParameterDescriptor`][django_service_specs.commands.argv.parameter_descriptor.ParameterDescriptor] per parameter, in declaration order.

    Never refuses a declaration: a parameter with no flat spelling is
    described with ``argv=False`` rather than left out, so a command can still
    say in ``--help`` that a spec takes something argv cannot send.
    """
    return tuple(_describe(param) for param in parameters)


def _describe(param: Parameter) -> ParameterDescriptor:
    return ParameterDescriptor(
        name=param.name,
        type=param.type,
        format=param.format,
        items=param.items if isinstance(param.items, str) else None,
        # The shape check's own rule for an absent argument, so the help says
        # "(required)" exactly where an omission is refused. Each condition is
        # held by its own test: test_required_means_an_omitted_option_is_refused
        # (the declaration) and test_a_required_parameter_with_a_default_is_not_required
        # (the default, reported or not).
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
    # Read from the type rather than from ``nested``, which alone is narrower
    # than "no honest option": an object with no ``fields`` and an array of
    # ``object``, ``array`` or ``file`` elements have no nested Parameters and
    # still no string that spells them. Held by
    # test_a_parameter_with_no_flat_spelling_has_no_option, one case per type,
    # and test_every_parameter_a_command_line_can_send_has_an_option.
    if param.type == "array":
        return param.items in _FLAT_ELEMENTS
    return param.type in _FLAT_TYPES


def _shown_default(default: Any) -> Any:
    """The default, where JSON spells it; otherwise ``UNSET``, so nothing is shown.

    One check rather than a list of exclusions: ``json.dumps`` refuses
    ``UNSET``, a callable and any other object it has no spelling for, and
    ``allow_nan=False`` refuses NaN and the infinities, which Python's encoder
    would otherwise write as tokens no JSON reader takes. Each is a case of
    test_a_default_with_no_json_spelling_is_not_reported.
    """
    try:
        json.dumps(default, allow_nan=False)
    except (TypeError, ValueError):
        return UNSET
    return default
