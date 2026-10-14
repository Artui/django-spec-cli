from __future__ import annotations

from django_service_specs.commands.argv.utils import destination, option_string


def test_an_option_is_two_dashes_and_the_name_with_dashes() -> None:
    assert option_string("due_at") == "--due-at"
    assert option_string("a-b") == "--a-b"


def test_a_destination_is_namespaced_away_from_the_command_s_own() -> None:
    # A parameter named like one of BaseCommand's options cannot overwrite it.
    assert destination("verbosity") == "spec_arg__verbosity"
