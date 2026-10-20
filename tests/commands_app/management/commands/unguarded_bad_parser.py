"""A ``SpecCommand`` that constructs, but whose parser cannot be built."""

from __future__ import annotations

from django_service_specs import (
    Parameter,
    Parameters,
    SelectorKind,
    SelectorSpec,
    SpecRegistry,
    Unrestricted,
)

from django_spec_cli.spec_command import SpecCommand


def _noop() -> None:
    return None


def _clashing_registry() -> SpecRegistry:
    registry = SpecRegistry()
    # ``--as-user`` is the command's own option, so no parameter may take it.
    registry.register(
        "clash",
        SelectorSpec(
            kind=SelectorKind.LIST,
            selector=_noop,
            permissions=[Unrestricted()],
            reads=Parameters.of(Parameter("as_user", "string")),
        ),
    )
    return registry


class Command(SpecCommand):
    registry = _clashing_registry()
