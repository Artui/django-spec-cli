from __future__ import annotations

import dataclasses
import datetime
import decimal
import math
from typing import Any, Literal

import pytest

from django_service_specs.adapters.dataclass.dataclass_validator import DataclassValidator
from django_service_specs.commands.argv.describe_parameters import describe_parameters
from django_service_specs.commands.argv.parameter_descriptor import ParameterDescriptor
from django_service_specs.parameters.parameters import Parameter, Parameters
from django_service_specs.types.unset import UNSET
from tests.commands.argv.utils import FLAT, UNSENDABLE


def describe_one(parameter: Parameter) -> ParameterDescriptor:
    (descriptor,) = describe_parameters(Parameters.of(parameter))
    return descriptor


def test_one_descriptor_per_parameter_in_declaration_order() -> None:
    parameters = FLAT + UNSENDABLE
    assert [d.name for d in describe_parameters(parameters)] == [p.name for p in parameters]


def test_every_parameter_a_command_line_can_send_has_an_option() -> None:
    assert all(d.argv for d in describe_parameters(FLAT))


@pytest.mark.parametrize("parameter", list(UNSENDABLE), ids=lambda p: p.name)
def test_a_parameter_with_no_flat_spelling_has_no_option(parameter: Parameter) -> None:
    # An object, an array of objects or of arrays, and a file: nothing a string
    # on a command line can honestly spell, so no option is invented for it.
    descriptor = describe_one(parameter)
    assert descriptor.argv is False
    assert descriptor.option is None


def test_the_declaration_is_carried_as_declared() -> None:
    descriptor = describe_one(
        Parameter(
            "prices",
            "array",
            items="string",
            format="decimal",
            choices=["1.5", "2.5"],
            choice_labels={"1.5": "Low"},
            minimum=1,
            maximum=3.5,
            min_length=1,
            max_length=4,
            help="What it costs.",
        )
    )
    assert descriptor == ParameterDescriptor(
        name="prices",
        type="array",
        format="decimal",
        items="string",
        required=False,
        default=UNSET,
        choices=("1.5", "2.5"),
        choice_labels=(("1.5", "Low"),),
        minimum=1,
        maximum=3.5,
        min_length=1,
        max_length=4,
        help="What it costs.",
        argv=True,
    )


def test_a_nested_array_reports_no_element_type() -> None:
    # ``items`` on a descriptor is a type name or nothing: the Parameters of a
    # row is no type a command line could show.
    rows = describe_one(Parameter("rows", "array", items=Parameters.of(Parameter("a", "string"))))
    assert rows.items is None


@pytest.mark.parametrize(
    "default",
    [None, "draft", 0, False, 2.5, ["a", "b"], {"k": 1}],
    ids=["none", "string", "zero", "false", "float", "list", "dict"],
)
def test_a_json_default_is_reported(default: Any) -> None:
    # ``None`` and the falsy values included: a declared default of ``None``
    # is a real default, which only ``UNSET`` is not.
    assert describe_one(Parameter("x", "any", default=default)).default == default


def _factory() -> str:
    return "computed"


@pytest.mark.parametrize(
    "default",
    [UNSET, _factory, object(), math.nan, math.inf, decimal.Decimal("1.5")],
    ids=["unset", "callable", "object", "nan", "infinity", "decimal"],
)
def test_a_default_with_no_json_spelling_is_not_reported(default: Any) -> None:
    # Printing a repr of a callable or a sentinel would be a concrete
    # falsehood in the help, and NaN and the infinities are no JSON value.
    assert describe_one(Parameter("x", "any", default=default)).default is UNSET


def test_required_means_an_omitted_option_is_refused() -> None:
    assert describe_one(Parameter("x", "string", required=True)).required is True
    assert describe_one(Parameter("x", "string")).required is False


@pytest.mark.parametrize("default", [_factory, "draft"], ids=["unreported", "reported"])
def test_a_required_parameter_with_a_default_is_not_required(default: Any) -> None:
    # The shape check refuses an absent required parameter only when no
    # default is declared, reported or not, so the help must not say otherwise.
    assert describe_one(Parameter("x", "any", required=True, default=default)).required is False


@dataclasses.dataclass
class _Note:
    pk: int
    title: str
    price: decimal.Decimal
    due_at: datetime.datetime
    status: Literal["draft", "published"] = "draft"
    pinned: bool = False
    tags: list[str] = dataclasses.field(default_factory=list)
    ids: list[int] = dataclasses.field(default_factory=list)


def test_a_dataclass_validator_s_parameters_are_described() -> None:
    descriptors = describe_parameters(DataclassValidator(_Note).parameters())
    by_name = {d.name: d for d in descriptors}
    assert list(by_name) == ["pk", "title", "price", "due_at", "status", "pinned", "tags", "ids"]
    assert by_name["pk"] == ParameterDescriptor(name="pk", type="integer", required=True)
    assert by_name["price"].format == "decimal"
    assert by_name["due_at"].format == "date-time"
    assert by_name["status"].choices == ("draft", "published")
    assert by_name["status"].default == "draft"
    assert by_name["pinned"].default is False
    # A factory's value is computed per instance, so it is no declared default.
    assert by_name["tags"].default is UNSET
    assert by_name["tags"].required is False
    assert by_name["ids"].items == "integer"
    assert all(d.argv for d in descriptors)
