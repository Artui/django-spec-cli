"""A ``SpecCommand`` that names no registry, so reading one fails after it constructed."""

from __future__ import annotations

from django_spec_cli.spec_command import SpecCommand


class Command(SpecCommand): ...
