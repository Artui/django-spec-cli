"""``exit_code_for`` - the exit status a refusal ends a ``SpecCommand`` run with."""

from __future__ import annotations

from django_service_specs import (
    AdditionalInputRequired,
    DispatchError,
    NotPermitted,
    PrincipalUnavailable,
    ServiceConflict,
    ServiceError,
    ServiceNotFound,
    ServiceValidationError,
)

from django_spec_cli.types.exit_code import ExitCode

_CODES: tuple[tuple[type[Exception], ExitCode], ...] = (
    (NotPermitted, ExitCode.NOT_PERMITTED),
    (PrincipalUnavailable, ExitCode.PRINCIPAL_UNAVAILABLE),
    (DispatchError, ExitCode.INVALID_ARGUMENTS),
    (ServiceValidationError, ExitCode.INVALID_ARGUMENTS),
    (ServiceNotFound, ExitCode.NOT_FOUND),
    (ServiceConflict, ExitCode.CONFLICT),
    (AdditionalInputRequired, ExitCode.INPUT_REQUIRED),
    (ServiceError, ExitCode.REFUSED),
)
"""Each refusal's code, read top to bottom, first match wins.

A subclass sits above its base, or the base's row would answer for it. Only
rows that change the answer are listed: ``InvalidArguments`` and
``ActionUnavailable`` take their base's code, so the base's row is theirs.
Coverage sees one expression, not eight rows, so each row is held by its own
case of test_every_refusal_the_kernel_raises_has_its_code."""


def exit_code_for(error: BaseException) -> ExitCode:
    """The [`ExitCode`][django_spec_cli.types.exit_code.ExitCode] ``error`` ends a run with.

    Every [`DispatchError`][django_service_specs.types.dispatch_error.DispatchError]
    and [`ServiceError`][django_service_specs.services.service_error.ServiceError]
    has a code, a subclass a later release adds included: it takes its
    nearest listed base's, so a new refusal of the call is ``INVALID_ARGUMENTS``
    as the HTTP transport answers it 400, and a new refusal by the operation
    ``REFUSED``. Anything else is ``ERROR``, which a ``SpecCommand`` never
    catches: an exception nobody declared is a bug, and its traceback is how
    it is found.
    """
    return next((code for kind, code in _CODES if isinstance(error, kind)), ExitCode.ERROR)
