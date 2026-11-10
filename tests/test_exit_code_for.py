from __future__ import annotations

from typing import Any

from django_service_specs import (
    REFUSALS,
    ActionUnavailable,
    AdditionalInputRequired,
    DispatchError,
    InvalidArguments,
    NotPermitted,
    PermissionCheck,
    PermissionCheckDenied,
    PrincipalUnavailable,
    SelectorKind,
    SelectorSpec,
    ServiceConflict,
    ServiceError,
    ServiceNotFound,
    ServiceValidationError,
    unanswered_refusals,
)

from django_spec_cli.exit_code_for import _CODES, exit_code_for
from django_spec_cli.types.exit_code import ExitCode

EXPECTED: dict[type[Exception], ExitCode] = {
    DispatchError: ExitCode.INVALID_ARGUMENTS,
    InvalidArguments: ExitCode.INVALID_ARGUMENTS,
    NotPermitted: ExitCode.NOT_PERMITTED,
    PermissionCheckDenied: ExitCode.NOT_PERMITTED,
    PrincipalUnavailable: ExitCode.PRINCIPAL_UNAVAILABLE,
    ServiceError: ExitCode.REFUSED,
    ServiceValidationError: ExitCode.INVALID_ARGUMENTS,
    ServiceNotFound: ExitCode.NOT_FOUND,
    ServiceConflict: ExitCode.CONFLICT,
    ActionUnavailable: ExitCode.CONFLICT,
    AdditionalInputRequired: ExitCode.INPUT_REQUIRED,
}
"""Every refusal the kernel raises, and its code, decided one by one."""


class _Denies(PermissionCheck):
    def has_permission(self, principal: Any, spec: Any) -> bool:
        return False


def _instance(kind: type[Exception]) -> Exception:
    if kind is InvalidArguments:
        return InvalidArguments({"title": ["Required."]})
    if kind is PermissionCheckDenied:
        # Built as ``authorize`` raises it: the check that answered and the spec declaring it.
        check = _Denies()
        spec = SelectorSpec(kind=SelectorKind.LIST, selector=list, permissions=[check])
        return PermissionCheckDenied(check=check, spec=spec)
    if kind is ServiceValidationError:
        return ServiceValidationError("Taken.")
    if kind is ActionUnavailable:
        return ActionUnavailable(code="archived")
    if kind is AdditionalInputRequired:
        return AdditionalInputRequired("Confirm.")
    return kind()


def test_every_refusal_the_kernel_raises_has_its_code() -> None:
    # A refusal a later release adds fails here until its code is chosen, not by its base.
    assert set(REFUSALS) == set(EXPECTED)
    assert {kind: exit_code_for(_instance(kind)) for kind in EXPECTED} == EXPECTED


def test_the_map_answers_every_refusal_and_shadows_no_row() -> None:
    # Covers the table and the function, where ERROR is the answer anything unmapped gets.
    assert unanswered_refusals(_CODES) == ()
    assert unanswered_refusals(exit_code_for, unanswered=ExitCode.ERROR) == ()


def test_a_subclass_nobody_listed_takes_its_nearest_base_s_code() -> None:
    class Throttled(DispatchError): ...

    class Archived(ServiceConflict): ...

    class Quota(ServiceError): ...

    assert exit_code_for(Throttled()) is ExitCode.INVALID_ARGUMENTS
    assert exit_code_for(Archived()) is ExitCode.CONFLICT
    assert exit_code_for(Quota()) is ExitCode.REFUSED


def test_anything_else_is_an_error() -> None:
    assert exit_code_for(RuntimeError("a bug")) is ExitCode.ERROR
    assert exit_code_for(KeyboardInterrupt()) is ExitCode.ERROR
