from __future__ import annotations

from django_service_specs import UnguardedReason, UnguardedSpec

# One clause per reason, indexed rather than branched on, so a member added
# without its sentence fails test_every_reason_has_its_own_wording instead of
# printing another member's.
_WHY = {
    UnguardedReason.UNRESTRICTED: "every permission check it declares is Unrestricted",
}


def unguarded_message(spec: UnguardedSpec, command_label: str) -> str:
    """The one-line report of ``spec``, served by the command ``command_label``."""
    return (
        f"{spec.name!r} in manage.py {command_label} authorizes nothing: "
        f"{_WHY[spec.reason]}, so any active user named by --as-user may run it."
    )
