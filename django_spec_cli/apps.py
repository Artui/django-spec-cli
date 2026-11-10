from __future__ import annotations

from django.apps import AppConfig
from django.core.checks import register

from django_spec_cli.checks import check_unguarded_specs


class DjangoSpecCliConfig(AppConfig):
    """Registers the system check over every ``SpecCommand``'s specs, and does nothing else."""

    name = "django_spec_cli"

    def ready(self) -> None:
        register(check_unguarded_specs)
