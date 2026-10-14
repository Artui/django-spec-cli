from __future__ import annotations

import argparse
import dataclasses
import datetime
import decimal
from typing import Any

import pytest

from django_service_specs.adapters.dataclass.dataclass_validator import DataclassValidator
from django_service_specs.commands.argv.parsed_arguments import parsed_arguments
from django_service_specs.parameters.check_arguments import check_arguments
from django_service_specs.parameters.coerce_flat import coerce_flat
from django_service_specs.parameters.invalid_arguments import InvalidArguments
from django_service_specs.parameters.parameters import Parameter, Parameters
from django_service_specs.validation.validation_context import ValidationContext
from tests.commands.argv.utils import FLAT, UNSENDABLE, parser_for


@dataclasses.dataclass
class _Entry:
    price: decimal.Decimal
    due_at: datetime.datetime
    done: bool
    ids: list[int]
    count: int


def parsed(parameters: Parameters, argv: list[str]) -> dict[str, Any]:
    return parsed_arguments(parser_for(parameters).parse_args(argv), parameters)


# One row per parameter type: the argv a person types, and the JSON a caller of
# the HTTP or MCP transport sends for the same value.
WIRE = [
    ("title", ["--title", "A note"], "A note"),
    ("title", ["--title", ""], ""),
    ("count", ["--count", "5"], 5),
    ("ratio", ["--ratio", "2.5"], 2.5),
    ("active", ["--active"], True),
    ("active", ["--no-active"], False),
    ("key", ["--key", "3"], "3"),
    ("price", ["--price", "19.99"], "19.99"),
    ("due_at", ["--due-at", "2026-03-01T09:30:00+02:00"], "2026-03-01T09:30:00+02:00"),
    ("on", ["--on", "2026-03-01"], "2026-03-01"),
    ("ids", ["--ids", "1", "--ids", "2"], [1, 2]),
    ("ids", ["--ids", "7"], [7]),
    ("ratios", ["--ratios", "0.5", "--ratios", "1"], [0.5, 1]),
    ("flags", ["--flags", "true", "--flags", "0"], [True, False]),
    ("tags", ["--tags", "a", "--tags", "b"], ["a", "b"]),
    ("prices", ["--prices", "1.10", "--prices", "2"], ["1.10", "2"]),
    ("anything", ["--anything", "x"], ["x"]),
]


@pytest.mark.parametrize(
    ("name", "argv", "json_value"), WIRE, ids=[" ".join(row[1]) for row in WIRE]
)
def test_argv_checks_to_exactly_what_the_json_wire_does(
    name: str, argv: list[str], json_value: Any
) -> None:
    # Through the real parser, then the one coercion and the one shape check
    # every transport shares.
    from_argv = check_arguments(FLAT, coerce_flat(FLAT, parsed(FLAT, argv)))
    from_json = check_arguments(FLAT, {name: json_value})
    assert from_argv == from_json
    assert list(from_argv) == [name]


def test_argv_validates_to_exactly_what_the_json_wire_does() -> None:
    # A Validator that decodes: the decimal and the offset-aware date-time are
    # the values it builds, so the two wires agree past the shape check too.
    validator = DataclassValidator(_Entry)
    parameters = validator.parameters()
    argv = ["--price", "19.99", "--due-at", "2026-03-01T09:30:00+02:00", "--no-done"]
    argv += ["--ids", "1", "--ids", "2", "--count", "3"]
    json_values = {
        "price": "19.99",
        "due_at": "2026-03-01T09:30:00+02:00",
        "done": False,
        "ids": [1, 2],
        "count": 3,
    }
    context = ValidationContext(principal=None)
    from_argv = validator.validate(
        check_arguments(parameters, coerce_flat(parameters, parsed(parameters, argv))), context
    )
    from_json = validator.validate(check_arguments(parameters, json_values), context)
    assert from_argv == from_json
    assert from_argv["price"] == decimal.Decimal("19.99")
    assert from_argv["due_at"].utcoffset() == datetime.timedelta(hours=2)


def test_an_omitted_option_is_absent_and_a_required_one_is_refused_as_http_refuses_it() -> None:
    parameters = Parameters.of(Parameter("title", "string", required=True))
    raw = parsed(parameters, [])
    assert raw == {}
    with pytest.raises(InvalidArguments) as from_argv:
        check_arguments(parameters, coerce_flat(parameters, raw))
    with pytest.raises(InvalidArguments) as from_json:
        check_arguments(parameters, {})
    assert from_argv.value.detail == from_json.value.detail


def test_a_boolean_crosses_the_shared_coercion_as_its_spelling() -> None:
    assert parsed(FLAT, ["--active"]) == {"active": "true"}
    assert parsed(FLAT, ["--no-active"]) == {"active": "false"}


def test_an_array_is_a_list_of_the_strings_given() -> None:
    assert parsed(FLAT, ["--ids", "1", "--ids", "x"]) == {"ids": ["1", "x"]}


def test_every_other_value_is_the_string_given() -> None:
    assert parsed(FLAT, ["--count", "5", "--title", ""]) == {"count": "5", "title": ""}


def test_a_value_given_by_destination_rather_than_argv_is_handed_on() -> None:
    # A caller filling the namespace itself, as ``call_command`` does from
    # keyword arguments, may hand over a value argparse never read: a string
    # for a boolean is left for ``coerce_flat``, and a boolean for a parameter
    # of another type is no spelling of one.
    namespace = argparse.Namespace(spec_arg__active="false", spec_arg__key=True)
    assert parsed_arguments(namespace, FLAT) == {"active": "false", "key": True}


def test_an_attribute_of_the_command_s_own_is_not_read() -> None:
    namespace = argparse.Namespace(verbosity=1, title="not a spec argument")
    assert parsed_arguments(namespace, FLAT) == {}


def test_a_parameter_with_no_option_still_meets_the_kernel_s_refusals() -> None:
    # No option is invented for it, and a caller that fills the namespace
    # itself still reaches coerce_flat's refusal by name; left out, a required
    # one is refused as missing, as it is for a JSON caller.
    parameters = UNSENDABLE + Parameters.of(Parameter("photo", "file", required=True))
    raw = parsed_arguments(argparse.Namespace(spec_arg__address="x"), parameters)
    assert raw == {"address": "x"}
    with pytest.raises(InvalidArguments) as nested:
        coerce_flat(parameters, raw)
    assert nested.value.detail["address"][0].code == "invalid"
    with pytest.raises(InvalidArguments) as missing:
        check_arguments(parameters, {})
    assert missing.value.detail["photo"][0].code == "required"
