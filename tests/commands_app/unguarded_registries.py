"""Registries for the unguarded-spec report, shared by its tests and its command modules.

One spec per shape the report has to tell apart, so a test can name the shape
it asserts: a real check, one ``Unrestricted``, two of them, and a real check
beside an ``Unrestricted``, which ``authorize`` runs and so guards the spec.
"""

from __future__ import annotations

from typing import Any

from django_service_specs.authorization.permission_check import PermissionCheck
from django_service_specs.authorization.unrestricted import Unrestricted
from django_service_specs.registry.spec_registry import SpecRegistry
from django_service_specs.specs.selector_spec import SelectorSpec
from django_service_specs.specs.service_spec import ServiceSpec
from django_service_specs.types.selector_kind import SelectorKind


class StaffOnly(PermissionCheck):
    """A check that refuses someone, so a spec declaring it is guarded."""

    def has_permission(self, principal: Any, spec: Any) -> bool:
        return bool(getattr(principal, "is_staff", False))


class OpenToAll(Unrestricted):
    """A project's own name for the explicit allow: still ``Unrestricted``."""


def _noop() -> None:
    return None


def service(*permissions: PermissionCheck) -> ServiceSpec:
    return ServiceSpec(service=_noop, permissions=list(permissions))


def selector(*permissions: PermissionCheck) -> SelectorSpec:
    return SelectorSpec(kind=SelectorKind.LIST, selector=_noop, permissions=list(permissions))


def mixed_registry() -> SpecRegistry:
    """Every shape, guarded ones between the unguarded, so order is observable."""
    registry = SpecRegistry()
    registry.register("guarded", service(StaffOnly()))
    registry.register("open_service", service(Unrestricted()))
    registry.register("mixed", service(Unrestricted(), StaffOnly()))
    registry.register("open_twice", selector(Unrestricted(), Unrestricted()))
    registry.register("guarded_after", selector(StaffOnly(), Unrestricted()))
    registry.register("open_subclass", selector(OpenToAll()))
    return registry
