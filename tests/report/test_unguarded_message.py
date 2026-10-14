from __future__ import annotations

import pytest

from django_service_specs.commands.report.unguarded_message import unguarded_message
from django_service_specs.commands.report.unguarded_spec import UnguardedSpec
from django_service_specs.types.unguarded_reason import UnguardedReason


def test_names_the_spec_and_the_command_the_operator_types() -> None:
    message = unguarded_message(UnguardedSpec("refund_order", UnguardedReason.UNRESTRICTED), "svc")
    assert message == (
        "'refund_order' in manage.py svc authorizes nothing: every permission check it "
        "declares is Unrestricted, so any active user named by --as-user may run it."
    )


@pytest.mark.parametrize("reason", list(UnguardedReason))
def test_every_reason_has_its_own_wording(reason: UnguardedReason) -> None:
    # A member added without a sentence would fail here rather than at the
    # first project whose spec falls under it.
    assert unguarded_message(UnguardedSpec("op", reason), "svc").startswith(
        "'op' in manage.py svc authorizes nothing: "
    )
