from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """The exit status of a [`SpecCommand`][django_spec_cli.spec_command.SpecCommand] run, a public contract."""  # noqa: E501

    SUCCESS = 0
    ERROR = 1
    USAGE = 2
    INVALID_ARGUMENTS = 3
    NOT_PERMITTED = 4
    PRINCIPAL_UNAVAILABLE = 5
    NOT_FOUND = 6
    CONFLICT = 7
    INPUT_REQUIRED = 8
    REFUSED = 9
