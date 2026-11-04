from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured

from django_spec_cli.report.utils import refused_message


def test_names_the_spec_and_the_command_then_the_kernel_s_reason() -> None:
    error = ImproperlyConfigured("ServiceSpec.service requires the keyword(s) ['tenant'].")
    assert refused_message("greet", "notes", error) == (
        "'greet' in manage.py notes cannot run as declared, and a run of it is refused: "
        "ServiceSpec.service requires the keyword(s) ['tenant']."
    )
