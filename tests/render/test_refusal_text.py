from __future__ import annotations

import pytest
from django_service_specs import (
    ActionUnavailable,
    AdditionalInputRequired,
    DispatchError,
    InvalidArguments,
    ServiceError,
    ServiceValidationError,
)

from django_spec_cli.render.refusal_text import refusal_text


@pytest.mark.parametrize(
    ("error", "text"),
    [
        (
            InvalidArguments({"title": ["Required."], "books": {1: {"isbn": ["Bad."]}}}),
            "Invalid arguments.\ntitle: Required.\nbooks.1.isbn: Bad.",
        ),
        (
            ServiceValidationError({"non_field_errors": ["Check it."]}),
            "Service validation error.\nCheck it.",
        ),
        (ServiceValidationError("The title is taken."), "The title is taken."),
        (ActionUnavailable("Archived.", code="archived"), "Archived. (code: archived)"),
        (
            AdditionalInputRequired("Confirm.", schema={"confirmed_by": {"type": "string"}}),
            "Confirm. Run it again with: --confirmed-by",
        ),
        (AdditionalInputRequired("Confirm."), "Confirm."),
        (ServiceError("[b]x[/b] [/x]"), "[b]x[/b] [/x]"),
    ],
)
def test_each_refusal_reads_as_its_message_and_its_fields(
    error: DispatchError | ServiceError, text: str
) -> None:
    assert refusal_text(error) == text
