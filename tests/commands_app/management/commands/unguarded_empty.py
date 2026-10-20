"""A command over an empty registry: nothing to report, and nothing to fail on."""

from __future__ import annotations

from django_service_specs import SpecRegistry

from django_spec_cli.spec_command import SpecCommand


class Command(SpecCommand):
    registry = SpecRegistry()
