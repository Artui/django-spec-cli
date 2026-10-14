"""The report of a registry's open specs, shared by a command's ``--explain`` and the system check."""

from django_service_specs.commands.report.unguarded_message import unguarded_message
from django_service_specs.commands.report.unguarded_spec import UnguardedSpec
from django_service_specs.commands.report.unguarded_specs import unguarded_specs

__all__ = [
    "UnguardedSpec",
    "unguarded_message",
    "unguarded_specs",
]
