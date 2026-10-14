from __future__ import annotations

import django_service_specs
from django_service_specs import (
    ActionUnavailable,
    AdditionalInputRequired,
    DispatchError,
    InvalidArguments,
    NotPermitted,
    PrincipalUnavailable,
    ServiceConflict,
    ServiceError,
    ServiceNotFound,
    ServiceValidationError,
    UnsupportedMediaType,
)
from django_service_specs.commands.exit_code_for import exit_code_for
from django_service_specs.types.exit_code import ExitCode

EXPECTED: dict[type[Exception], ExitCode] = {
    DispatchError: ExitCode.INVALID_ARGUMENTS,
    InvalidArguments: ExitCode.INVALID_ARGUMENTS,
    UnsupportedMediaType: ExitCode.INVALID_ARGUMENTS,
    NotPermitted: ExitCode.NOT_PERMITTED,
    PrincipalUnavailable: ExitCode.PRINCIPAL_UNAVAILABLE,
    ServiceError: ExitCode.REFUSED,
    ServiceValidationError: ExitCode.INVALID_ARGUMENTS,
    ServiceNotFound: ExitCode.NOT_FOUND,
    ServiceConflict: ExitCode.CONFLICT,
    ActionUnavailable: ExitCode.CONFLICT,
    AdditionalInputRequired: ExitCode.INPUT_REQUIRED,
}
"""Every refusal the package defines, and its code, decided one by one."""


def _family(base: type[Exception]) -> set[type[Exception]]:
    found = {base}
    for sub in base.__subclasses__():
        found |= _family(sub)
    return found


def _instance(kind: type[Exception]) -> Exception:
    if kind is InvalidArguments:
        return InvalidArguments({"title": ["Required."]})
    if kind is ServiceValidationError:
        return ServiceValidationError("Taken.")
    if kind is ActionUnavailable:
        return ActionUnavailable(code="archived")
    if kind is AdditionalInputRequired:
        return AdditionalInputRequired("Confirm.")
    return kind()


def test_every_refusal_in_the_package_has_its_code() -> None:
    # The package's own, read from the class tree: a refusal a later release
    # adds is not in EXPECTED, and fails here until its code is decided,
    # rather than falling through to its base's silently.
    defined = {
        kind
        for kind in _family(DispatchError) | _family(ServiceError)
        if kind.__module__.startswith(django_service_specs.__name__ + ".")
    }
    assert defined == set(EXPECTED)
    assert {kind: exit_code_for(_instance(kind)) for kind in defined} == EXPECTED


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
