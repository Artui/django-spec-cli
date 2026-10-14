from __future__ import annotations

import argparse

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy

from django_service_specs.commands.argv.add_spec_arguments import add_spec_arguments
from django_service_specs.parameters.parameters import Parameter, Parameters
from tests.commands.argv.utils import FLAT, UNSENDABLE, parser_for

# Django's BaseCommand options and the ones a spec command adds, as a caller
# passes them.
RESERVED = (
    "--as-user",
    "--json",
    "--table",
    "--version",
    "--verbosity",
    "--settings",
    "--pythonpath",
    "--traceback",
    "--no-color",
    "--force-color",
    "--skip-checks",
)


def test_every_sendable_parameter_has_its_option() -> None:
    parser = parser_for(FLAT)
    namespace = parser.parse_args(
        ["--title", "t", "--due-at", "2026-01-01T00:00:00+02:00", "--ids", "1", "--active"]
    )
    assert vars(namespace) == {
        "spec_arg__title": "t",
        "spec_arg__due_at": "2026-01-01T00:00:00+02:00",
        "spec_arg__ids": ["1"],
        "spec_arg__active": True,
    }


def test_an_omitted_option_is_absent_from_the_namespace() -> None:
    # Absent, not ``None``, ``""`` or ``False``: the shape check decides what an
    # omitted argument means, as it does for a JSON caller who left a key out.
    assert vars(parser_for(FLAT).parse_args([])) == {}


def test_an_empty_string_is_kept_apart_from_an_omitted_option() -> None:
    assert vars(parser_for(FLAT).parse_args(["--title", ""])) == {"spec_arg__title": ""}


@pytest.mark.parametrize("parameter", list(UNSENDABLE), ids=lambda p: p.name)
def test_a_parameter_with_no_flat_spelling_gets_no_option(parameter: Parameter) -> None:
    parser = parser_for(Parameters.of(parameter))
    option = "--" + parameter.name
    assert option not in parser.format_help()
    _namespace, extra = parser.parse_known_args([option, "x"])
    assert extra == [option, "x"]


def test_every_value_stays_the_string_given() -> None:
    # Coerced later by ``coerce_flat``, never by argparse, so a value argparse
    # would have refused as an int reaches the kernel's own refusal.
    namespace = parser_for(FLAT).parse_args(["--count", "five", "--ratio", "1e3"])
    assert vars(namespace) == {"spec_arg__count": "five", "spec_arg__ratio": "1e3"}


def test_a_boolean_is_a_pair_of_flags() -> None:
    parser = parser_for(FLAT)
    assert vars(parser.parse_args(["--active"])) == {"spec_arg__active": True}
    assert vars(parser.parse_args(["--no-active"])) == {"spec_arg__active": False}


def test_an_array_is_a_repeated_option() -> None:
    namespace = parser_for(FLAT).parse_args(["--ids", "1", "--ids", "2", "--tags", "a"])
    assert vars(namespace) == {"spec_arg__ids": ["1", "2"], "spec_arg__tags": ["a"]}


def test_a_required_parameter_is_not_required_by_argparse() -> None:
    # The shape check owns "missing", so the refusal is the one HTTP gives.
    parser = parser_for(Parameters.of(Parameter("title", "string", required=True)))
    assert vars(parser.parse_args([])) == {}
    assert "(required)" in parser.format_help()


def test_a_required_parameter_with_a_default_is_not_shown_as_required() -> None:
    parser = parser_for(Parameters.of(Parameter("title", "string", required=True, default="x")))
    assert "required" not in parser.format_help()


def test_a_choice_is_listed_and_left_to_the_shape_check() -> None:
    status = Parameter(
        "status", "string", choices=["draft", "published"], choice_labels={"draft": "Draft"}
    )
    parser = parser_for(Parameters.of(status))
    assert "one of: draft (Draft), published" in _flat_help(parser)
    # Not refused by argparse: the shape check's refusal is the only one, so
    # one mistake has one message and one exit code.
    assert vars(parser.parse_args(["--status", "bogus"])) == {"spec_arg__status": "bogus"}


def test_a_choice_that_is_not_a_string_is_listed_as_json() -> None:
    parser = parser_for(Parameters.of(Parameter("level", "integer", choices=[1, 2])))
    assert "one of: 1, 2" in _flat_help(parser)
    parser = parser_for(Parameters.of(Parameter("x", "any", default=None)))
    assert "default: null" in _flat_help(parser)


def test_an_empty_string_default_is_shown_quoted() -> None:
    # Bare, it would read as no default at all.
    parser = parser_for(Parameters.of(Parameter("note", "string", default="")))
    assert '--note STRING (default: "")' in _flat_help(parser)


def test_the_help_describes_what_the_value_takes() -> None:
    parameters = Parameters.of(
        Parameter("count", "integer", minimum=1, maximum=10, help="How many."),
        Parameter("ids", "array", items="integer", min_length=1, max_length=5),
        Parameter("status", "string", default="draft"),
        Parameter("active", "boolean", default=True),
        Parameter("due_at", "string", format="date-time"),
        Parameter("key", "any"),
        Parameter("anything", "array"),
    )
    help_text = _flat_help(parser_for(parameters))
    assert "--count INTEGER How many. (minimum 1; maximum 10)" in help_text
    assert "--ids INTEGER (repeat the option for each element; at least 1; at most 5)" in help_text
    assert "--status STRING (default: draft)" in help_text
    assert "--active, --no-active (default: true)" in help_text
    assert "--due-at DATE-TIME" in help_text
    assert "--key VALUE" in help_text
    assert "--anything VALUE (repeat the option for each element)" in help_text
    # The namespaced destination never leaks into the help.
    assert "SPEC_ARG" not in help_text


def test_a_percent_sign_in_any_help_text_is_printed_as_written() -> None:
    # argparse formats help with ``%``, so an unescaped one raises or eats text.
    parameters = Parameters.of(
        Parameter(
            "rate",
            "string",
            help="A 50% cut, or %(prog)s.",
            choices=["10%", "20%"],
            choice_labels={"10%": "Ten %"},
            default="10%",
        )
    )
    help_text = _flat_help(parser_for(parameters))
    assert "A 50% cut, or %(prog)s. (one of: 10% (Ten %), 20%; default: 10%)" in help_text


def test_a_parameter_named_like_a_base_command_option_cannot_overwrite_it() -> None:
    # ``verbosity`` and ``settings`` are BaseCommand's destinations; a spec
    # parameter's lands under its own namespace beside them.
    parameters = Parameters.of(Parameter("verbosity", "string"), Parameter("settings", "string"))
    parser = parser_for(parameters)
    parser.set_defaults(verbosity=1, settings=None)
    namespace = parser.parse_args(["--verbosity", "loud", "--settings", "mine"])
    assert namespace.verbosity == 1
    assert namespace.settings is None
    assert namespace.spec_arg__verbosity == "loud"


@pytest.mark.parametrize(
    ("parameter", "option"),
    [
        (Parameter("as_user", "integer"), "--as-user"),
        (Parameter("json", "boolean"), "--json"),
        # A boolean claims its negative too, which may be Django's own.
        (Parameter("color", "boolean"), "--no-color"),
        # Every argparse parser owns its help, whatever the caller reserves.
        (Parameter("help", "string"), "--help"),
    ],
    ids=["as-user", "json", "negative-flag", "help"],
)
def test_an_option_the_command_owns_is_refused(parameter: Parameter, option: str) -> None:
    with pytest.raises(ImproperlyConfigured) as caught:
        parser_for(Parameters.of(parameter), reserved=RESERVED)
    assert str(caught.value) == (
        f"Parameter {parameter.name!r}: the option {option!r} is the command's own; "
        "rename the parameter."
    )


@pytest.mark.parametrize(
    ("parameters", "first", "second", "option"),
    [
        (
            Parameters.of(Parameter("a_b", "string"), Parameter("a-b", "string")),
            "a_b",
            "a-b",
            "--a-b",
        ),
        (
            Parameters.of(Parameter("x", "boolean"), Parameter("no_x", "string")),
            "x",
            "no_x",
            "--no-x",
        ),
        (
            Parameters.of(Parameter("no_x", "string"), Parameter("x", "boolean")),
            "no_x",
            "x",
            "--no-x",
        ),
    ],
    ids=["underscore-and-dash", "negative-flag-after", "negative-flag-before"],
)
def test_two_parameters_mapping_to_one_option_are_refused(
    parameters: Parameters, first: str, second: str, option: str
) -> None:
    with pytest.raises(ImproperlyConfigured) as caught:
        parser_for(parameters)
    assert str(caught.value) == (
        f"Parameters {first!r} and {second!r} both map to the option {option!r}; "
        "rename one of them."
    )


def test_a_refused_parameter_adds_no_option() -> None:
    # Every option is checked before the first is added, so a refused spec
    # leaves the parser as it was rather than half-built.
    parser = argparse.ArgumentParser()
    parameters = Parameters.of(Parameter("title", "string"), Parameter("json", "string"))
    with pytest.raises(ImproperlyConfigured):
        add_spec_arguments(parser, parameters, reserved=["--json"])
    assert "--title" not in parser.format_help()


def test_a_parameter_with_no_option_is_never_refused_for_one() -> None:
    # A file named ``json`` has no option, so it claims none of the command's.
    parser_for(Parameters.of(Parameter("json", "file")), reserved=RESERVED)


def _flat_help(parser: argparse.ArgumentParser) -> str:
    # argparse wraps help to the terminal's width; one line per option is what
    # the assertions read.
    return " ".join(parser.format_help().split())


@pytest.mark.parametrize(
    ("kind", "choices", "labels", "shown"),
    [
        # ``1 == True`` to Python; the declaration keeps them two choices.
        ("integer", [True, 1], [(True, "Yes")], "one of: true (Yes), 1)"),
        ("string", ["a", "b"], {"a": "Ay"}, "one of: a (Ay), b)"),
    ],
    ids=["equal-across-types", "unlabelled"],
)
def test_a_choice_is_shown_with_its_own_label(
    kind: str, choices: list[object], labels: object, shown: str
) -> None:
    parameter = Parameter("x", kind, choices=choices, choice_labels=labels)
    assert shown in _flat_help(parser_for(Parameters.of(parameter)))


def test_a_lazy_help_text_is_rendered() -> None:
    parameters = Parameters.of(Parameter("title", "string", help=gettext_lazy("The title.")))
    assert "--title STRING The title." in _flat_help(parser_for(parameters))
