from __future__ import annotations

import dataclasses

import pytest

from django_service_specs.commands.argv.parameter_descriptor import ParameterDescriptor
from django_service_specs.types.unset import UNSET


def test_the_option_is_the_name_with_dashes() -> None:
    assert ParameterDescriptor(name="due_at", type="string").option == "--due-at"


def test_a_parameter_with_no_option_has_none() -> None:
    assert ParameterDescriptor(name="meta", type="object", argv=False).option is None


def test_a_descriptor_reports_no_default_unless_one_is_given() -> None:
    assert ParameterDescriptor(name="x", type="string").default is UNSET


def test_a_descriptor_is_frozen() -> None:
    descriptor = ParameterDescriptor(name="x", type="string")
    with pytest.raises(dataclasses.FrozenInstanceError):
        descriptor.name = "y"  # ty: ignore[invalid-assignment]
