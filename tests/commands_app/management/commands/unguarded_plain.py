from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from tests.commands_app.unguarded_registries import mixed_registry


class Command(BaseCommand):
    registry = mixed_registry()

    def handle(self, *args: Any, **options: Any) -> None: ...
