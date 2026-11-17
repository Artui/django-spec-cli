from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django_service_specs import (
    ActionUnavailable,
    AdditionalInputRequired,
    DispatchError,
    InvalidArguments,
    ServiceError,
    ServiceValidationError,
    refusal_messages,
)

from django_spec_cli.argv.utils import option_string


def refusal_text(error: DispatchError | ServiceError) -> str:
    """A refusal as the text a person reads: its message, and each refused field on a line."""
    if isinstance(error, InvalidArguments):
        return _with_fields(error.message, error.detail)
    if isinstance(error, ServiceValidationError) and isinstance(error.detail, Mapping | list):
        return _with_fields(error.message, error.detail)
    if isinstance(error, ActionUnavailable):
        return f"{error.message} (code: {error.code})"
    if isinstance(error, AdditionalInputRequired) and error.schema:
        options = ", ".join(option_string(key) for key in error.schema)
        return f"{error.message} Run it again with: {options}"
    return str(error.message)


def _with_fields(header: Any, detail: Any) -> str:
    """``header``, then each message in ``detail`` on its own line, after its path."""
    rows = [
        f"{'.'.join(path)}: {text}" if path else text for path, text in refusal_messages(detail)
    ]
    return "\n".join([str(header), *rows])
