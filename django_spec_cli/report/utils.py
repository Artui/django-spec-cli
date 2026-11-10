from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured


def refused_message(spec_name: str, command_label: str, error: ImproperlyConfigured) -> str:
    """The one-line report of ``spec_name``, which ``check_seeds`` refused with ``error``."""
    return (
        f"{spec_name!r} in manage.py {command_label} cannot run as declared, and a run of it "
        f"is refused: {error}"
    )
