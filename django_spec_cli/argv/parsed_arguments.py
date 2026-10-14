"""``parsed_arguments`` - the options argparse read, as the raw arguments ``coerce_flat`` takes."""

from __future__ import annotations

import argparse
from typing import Any

from django_service_specs.commands.argv.utils import destination
from django_service_specs.parameters.parameters import Parameters


def parsed_arguments(namespace: argparse.Namespace, parameters: Parameters) -> dict[str, Any]:
    """The spec's arguments from a namespace filled by [`add_spec_arguments`][django_service_specs.commands.argv.add_spec_arguments.add_spec_arguments]'s options.

    The raw dict a command hands to
    [`coerce_flat`][django_service_specs.parameters.coerce_flat.coerce_flat],
    keyed by parameter name, so argv crosses the one coercion and the one
    shape check every transport shares and is refused, or validated, exactly
    as the same values off a JSON wire would be:

    - **An omitted option is absent**, so the shape check decides what its
      absence means, as it does for a JSON caller who left the key out.
    - A ``boolean`` is the string ``"true"`` or ``"false"``: one of the four
      spellings ``coerce_flat`` reads, rather than a Python ``bool`` only this
      transport would hand on.
    - An ``array`` is the list of strings given, one per repeated option.
    - Everything else is the string given, an empty one included.

    Only the namespaced destinations are read, so a command's own options in
    the same namespace - ``verbosity``, ``settings`` - never become arguments.
    A value set there by a caller other than argparse, as ``call_command``
    does with keyword arguments, is handed on as it was set, except that a
    ``bool`` for a ``boolean`` is spelled as argparse's would have been.
    """
    values = vars(namespace)
    raw: dict[str, Any] = {}
    for param in parameters:
        key = destination(param.name)
        if key not in values:
            continue
        value = values[key]
        # Each condition is held by its own case of
        # test_a_value_given_by_destination_rather_than_argv_is_handed_on: a
        # string for a boolean stays the string, and a ``bool`` for an ``any``
        # stays the ``bool``.
        if param.type == "boolean" and isinstance(value, bool):
            value = "true" if value else "false"
        raw[param.name] = value
    return raw
