"""A command over an empty registry: nothing to report, and nothing to fail on."""

from __future__ import annotations

from django_service_specs.commands.spec_command import SpecCommand
from django_service_specs.registry.spec_registry import SpecRegistry


class Command(SpecCommand):
    registry = SpecRegistry()
