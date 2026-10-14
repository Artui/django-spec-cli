from __future__ import annotations

from django_service_specs.types.exit_code import ExitCode


def test_each_code_is_the_number_the_docs_publish() -> None:
    # A script branches on the number, so renumbering a member is a breaking
    # change this pins.
    assert {member.name: int(member) for member in ExitCode} == {
        "SUCCESS": 0,
        "ERROR": 1,
        "USAGE": 2,
        "INVALID_ARGUMENTS": 3,
        "NOT_PERMITTED": 4,
        "PRINCIPAL_UNAVAILABLE": 5,
        "NOT_FOUND": 6,
        "CONFLICT": 7,
        "INPUT_REQUIRED": 8,
        "REFUSED": 9,
    }
