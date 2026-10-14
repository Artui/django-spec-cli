"""``ExitCode`` - what a ``SpecCommand``'s exit status says about the run."""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """The exit status of a [`SpecCommand`][django_service_specs.commands.spec_command.SpecCommand] run, a public contract.

    A script branches on these, so a member's number never changes and a
    number is never reused. Each says who refused and what the caller can do
    about it, read the way the HTTP transport reads the same refusals:

    | Code | Member | The run | Raised for |
    | --- | --- | --- | --- |
    | 0 | `SUCCESS` | ran, and its result was written | |
    | 1 | `ERROR` | failed in a way nobody declared | anything else, with a traceback |
    | 2 | `USAGE` | never started: the command line was malformed | argparse's own refusals |
    | 3 | `INVALID_ARGUMENTS` | was refused its arguments | `InvalidArguments`, `ServiceValidationError`, any other `DispatchError` |
    | 4 | `NOT_PERMITTED` | was refused to the principal | `NotPermitted` |
    | 5 | `PRINCIPAL_UNAVAILABLE` | had nobody to run as | `PrincipalUnavailable` |
    | 6 | `NOT_FOUND` | found no row to act on | a `not_found` result, `ServiceNotFound` |
    | 7 | `CONFLICT` | was refused by the row's current state | `ServiceConflict`, `ActionUnavailable` |
    | 8 | `INPUT_REQUIRED` | needs a value it was not given | `AdditionalInputRequired` |
    | 9 | `REFUSED` | was refused by the operation's own rule | any other `ServiceError` |

    ``INPUT_REQUIRED`` has its own code because a command line cannot ask:
    the operator re-runs the command with the option the message names, and
    a script that knows it may answer does so. ``ActionUnavailable`` is a
    conflict, as its base is; its ``code`` is in the message.

    ``USAGE`` is the command line's: ``manage.py`` exits 2 on a malformed
    line. Through ``call_command`` Django raises every parser error as a
    ``CommandError`` with ``returncode`` 1 instead, and the command's own
    usage errors take the same path, so a caller there reads a usage error
    by its message.
    """

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
