from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """The exit status of a [`SpecCommand`][django_spec_cli.spec_command.SpecCommand] run, a public contract.

    A script branches on these, so a member's number never changes and a
    number is never reused. Each says who refused and what the caller can do
    about it, read the way the HTTP transport reads the same refusals:

    - ``0`` ``SUCCESS``: the run ran, and its result was written.
    - ``1`` ``ERROR``: it failed in a way nobody declared; raised for anything else,
      with a traceback.
    - ``2`` ``USAGE``: it never started, the command line was malformed; argparse's own
      refusals.
    - ``3`` ``INVALID_ARGUMENTS``: it was refused its arguments; raised for
      ``InvalidArguments``, ``ServiceValidationError`` and any other ``DispatchError``.
    - ``4`` ``NOT_PERMITTED``: it was refused to the principal; raised for ``NotPermitted``
      and ``PermissionCheckDenied``.
    - ``5`` ``PRINCIPAL_UNAVAILABLE``: it had nobody to run as; raised for
      ``PrincipalUnavailable``.
    - ``6`` ``NOT_FOUND``: it found no row to act on; raised for a ``not_found`` result and
      ``ServiceNotFound``.
    - ``7`` ``CONFLICT``: it was refused by the row's current state; raised for
      ``ServiceConflict`` and ``ActionUnavailable``.
    - ``8`` ``INPUT_REQUIRED``: it needs a value it was not given; raised for
      ``AdditionalInputRequired``.
    - ``9`` ``REFUSED``: it was refused by the operation's own rule; raised for any other
      ``ServiceError``.

    ``INPUT_REQUIRED`` has its own code because a command line cannot ask:
    the operator re-runs the command with the option the message names, and
    a script that knows it may answer does so. ``ActionUnavailable`` is a
    conflict, as its base is; its ``code`` is in the message.

    ``USAGE`` is the command line's: ``manage.py`` exits 2 on a malformed
    line. Through ``call_command`` Django raises every parser error as a
    ``CommandError`` with ``returncode`` 1 instead, and the command's own
    usage errors take the same path, so a caller there reads a usage error
    by its message.
    """  # noqa: E501

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
