"""``exit_code_for`` - the exit status a refusal ends a ``SpecCommand`` run with."""

from __future__ import annotations

from django_service_specs.authorization.not_permitted import NotPermitted
from django_service_specs.authorization.principal_unavailable import PrincipalUnavailable
from django_service_specs.services.additional_input_required import AdditionalInputRequired
from django_service_specs.services.service_conflict import ServiceConflict
from django_service_specs.services.service_error import ServiceError
from django_service_specs.services.service_not_found import ServiceNotFound
from django_service_specs.services.service_validation_error import ServiceValidationError
from django_service_specs.types.dispatch_error import DispatchError
from django_service_specs.types.exit_code import ExitCode

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
case of test_every_refusal_in_the_package_has_its_code."""


def exit_code_for(error: BaseException) -> ExitCode:
    """The [`ExitCode`][django_service_specs.types.exit_code.ExitCode] ``error`` ends a run with.

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
