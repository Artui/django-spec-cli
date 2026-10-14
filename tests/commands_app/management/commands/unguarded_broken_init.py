"""A ``SpecCommand`` whose construction fails, after its module imported cleanly."""

from __future__ import annotations

from typing import Any

from django_service_specs.commands.spec_command import SpecCommand
from tests.commands_app.unguarded_registries import mixed_registry


class Command(SpecCommand):
    registry = mixed_registry()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise ValueError("this command cannot be constructed")
