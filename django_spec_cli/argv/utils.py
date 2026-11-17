from __future__ import annotations

import inspect
from dataclasses import replace
from typing import Any

from django_service_specs import (
    Parameters,
    PoolSeeds,
    SelectorSpec,
    ServiceSpec,
    build_call_context,
    spec_caller_input_schema,
)

from django_spec_cli.types.cli_transport import CLI_TRANSPORT

DESTINATION_PREFIX = "spec_arg__"
"""Where a spec argument lands in argparse's namespace.

A spec parameter may be named ``verbosity``, ``settings`` or ``traceback``, and
``BaseCommand`` keeps its own options in the same namespace under exactly those
names. Prefixed, the two never meet, so a spec argument cannot change how the
command itself runs. ``parsed_arguments`` is the only reader."""


def destination(name: str) -> str:
    """The namespace attribute a parameter's option stores its value under."""
    return DESTINATION_PREFIX + name


def option_string(name: str) -> str:
    """The option a parameter is sent with: ``due_at`` is ``--due-at``."""
    return "--" + name.replace("_", "-")


def call_context() -> dict[str, Any]:
    """A new context for the command's own reads and one run, stamped ``cli``."""
    return build_call_context(CLI_TRANSPORT)


def sendable(
    spec: ServiceSpec | SelectorSpec, pool_seeds: PoolSeeds, call_context: dict[str, Any]
) -> Parameters:
    """What a caller may send, as the kernel reads it: required only where dispatch demands it."""
    schema = spec_caller_input_schema(spec, pool_seeds=pool_seeds, call_context=call_context)
    required = frozenset(schema.get("required", ()))
    return Parameters.of(
        *(
            param if param.name in required else replace(param, required=False)
            for param in spec.parameters(call_context=call_context)
            if param.name in schema["properties"]
        )
    )


def spec_summary(spec: ServiceSpec | SelectorSpec, name: str) -> str:
    """The first paragraph of the spec callable's own doc, and whether it reads or writes."""
    call = spec.selector if isinstance(spec, SelectorSpec) else spec.service
    kind = "read" if isinstance(spec, SelectorSpec) else "write"
    doc = call.__doc__ if inspect.isfunction(call) or inspect.ismethod(call) else None
    first = " ".join(inspect.cleandoc(doc).split("\n\n")[0].split()) if doc else name
    return f"{first} ({kind})"
