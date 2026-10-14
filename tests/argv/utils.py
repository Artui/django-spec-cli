from __future__ import annotations

import argparse
from collections.abc import Collection

from django_service_specs.commands.argv.add_spec_arguments import add_spec_arguments
from django_service_specs.parameters.parameters import Parameter, Parameters

ROW = Parameters.of(Parameter("title", "string", required=True))

FLAT = Parameters.of(
    Parameter("title", "string"),
    Parameter("count", "integer"),
    Parameter("ratio", "number"),
    Parameter("active", "boolean"),
    Parameter("key", "any"),
    Parameter("price", "string", format="decimal"),
    Parameter("due_at", "string", format="date-time"),
    Parameter("on", "string", format="date"),
    Parameter("ids", "array", items="integer"),
    Parameter("ratios", "array", items="number"),
    Parameter("flags", "array", items="boolean"),
    Parameter("tags", "array", items="string"),
    Parameter("prices", "array", items="string", format="decimal"),
    Parameter("anything", "array"),
)
"""Every parameter a command line can send: each one has an option."""

UNSENDABLE = Parameters.of(
    Parameter("meta", "object"),
    Parameter("address", "object", fields=ROW),
    Parameter("upload", "file"),
    Parameter("uploads", "array", items="file"),
    Parameter("rows", "array", items=ROW),
    Parameter("blobs", "array", items="object"),
    Parameter("grid", "array", items="array"),
)
"""Every parameter a command line cannot send: none has an option."""


def parser_for(
    parameters: Parameters, *, reserved: Collection[str] = ()
) -> argparse.ArgumentParser:
    # exit_on_error=False so an option argparse does not know raises rather than exits.
    parser = argparse.ArgumentParser(prog="svc", exit_on_error=False)
    add_spec_arguments(parser, parameters, reserved=reserved)
    return parser
