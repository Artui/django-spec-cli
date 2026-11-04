"""Helpers the system check and ``SpecCommand`` share: the sentence for a spec the kernel refuses."""

from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured


def refused_message(spec_name: str, command_label: str, error: ImproperlyConfigured) -> str:
    """The one-line report of ``spec_name``, which ``check_seeds`` refused with ``error``.

    ``command_label`` is the name an operator types after ``manage.py``. The
    system check and a run of the spec both print this, so the warning a
    project sees before a run reads as the refusal the run ends with.
    """
    return (
        f"{spec_name!r} in manage.py {command_label} cannot run as declared, and a run of it "
        f"is refused: {error}"
    )
