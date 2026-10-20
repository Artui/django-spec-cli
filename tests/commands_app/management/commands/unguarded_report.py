"""A command over a registry holding every shape the unguarded-spec report tells apart."""

from __future__ import annotations

from django_spec_cli.spec_command import SpecCommand
from tests.commands_app.unguarded_registries import mixed_registry


class Command(SpecCommand):
    registry = mixed_registry()
