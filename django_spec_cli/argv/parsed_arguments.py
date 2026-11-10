from __future__ import annotations

import argparse
from typing import Any

from django_service_specs import Parameters

from django_spec_cli.argv.utils import destination


def parsed_arguments(namespace: argparse.Namespace, parameters: Parameters) -> dict[str, Any]:
    """The spec's arguments from a namespace filled by [`add_spec_arguments`][django_spec_cli.argv.add_spec_arguments.add_spec_arguments]'s options."""  # noqa: E501
    values = vars(namespace)
    raw: dict[str, Any] = {}
    for param in parameters:
        key = destination(param.name)
        if key not in values:
            continue
        value = values[key]
        if param.type == "boolean" and isinstance(value, bool):
            value = "true" if value else "false"
        raw[param.name] = value
    return raw
