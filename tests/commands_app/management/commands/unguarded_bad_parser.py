"""A ``SpecCommand`` that constructs, but whose parser cannot be built."""

from __future__ import annotations

from django_service_specs.authorization.unrestricted import Unrestricted
from django_service_specs.commands.spec_command import SpecCommand
from django_service_specs.parameters.parameters import Parameter, Parameters
from django_service_specs.registry.spec_registry import SpecRegistry
from django_service_specs.specs.selector_spec import SelectorSpec
from django_service_specs.types.selector_kind import SelectorKind


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
