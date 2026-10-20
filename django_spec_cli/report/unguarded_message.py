"""``unguarded_message`` - the sentence that reports one unguarded spec."""

from __future__ import annotations

from django_service_specs.registry.unguarded_spec import UnguardedSpec
from django_service_specs.types.unguarded_reason import UnguardedReason

# One clause per reason, indexed rather than branched on, so a member added
# without its sentence fails test_every_reason_has_its_own_wording instead of
# printing another member's.
_WHY = {
    UnguardedReason.UNRESTRICTED: "every permission check it declares is Unrestricted",
}


def unguarded_message(spec: UnguardedSpec, command_label: str) -> str:
    """The one-line report of ``spec``, served by the command ``command_label``.

    ``command_label`` is the name an operator types after ``manage.py``. The
    system check and the command's own listing both print this, so the two
    read the same.

    The sentence says "any active user": dispatch refuses a deactivated
    principal whatever the spec's checks allow, so an open spec is open to
    every account that can still sign in, and to no other.
    """
    return (
        f"{spec.name!r} in manage.py {command_label} authorizes nothing: "
        f"{_WHY[spec.reason]}, so any active user named by --as-user may run it."
    )
