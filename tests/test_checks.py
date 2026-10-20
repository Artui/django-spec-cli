"""The unguarded-spec system check, run over this suite's own command modules.

Other tests add command modules to the same app, so every assertion here is
filtered to the commands this file owns - the ``unguarded_`` ones - and none
says that a message is absent project-wide.
"""

from __future__ import annotations

import importlib
import io
import subprocess
import sys
from pathlib import Path

import pytest
from django.apps import apps
from django.core.checks import CheckMessage, Warning
from django.core.management import call_command, get_commands, load_command_class
from django.core.management.base import SystemCheckError
from django.test import override_settings

from django_service_specs.checks import check_unguarded_specs
from django_service_specs.commands.report.unguarded_message import unguarded_message
from django_service_specs.registry.unguarded_spec import UnguardedSpec
from django_service_specs.types.unguarded_reason import UnguardedReason

REPO_ROOT = Path(__file__).resolve().parents[1]
APP = "tests.commands_app"
OWN = "unguarded_"
HINT = (
    "Declare a PermissionCheck that refuses someone in the spec's permissions, or add "
    "'django_service_specs.W001' to SILENCED_SYSTEM_CHECKS if the spec is meant to be open."
)


def _command_class(name: str) -> type:
    return importlib.import_module(f"{APP}.management.commands.{name}").Command


def _own(messages: list[CheckMessage]) -> list[CheckMessage]:
    return [
        message
        for message in messages
        if message.id is not None
        and message.id.startswith("django_service_specs.")
        and f"'{OWN}" in message.msg
    ]


def _own_w001(messages: list[CheckMessage]) -> list[CheckMessage]:
    return [
        message
        for message in messages
        if message.id == "django_service_specs.W001"
        and message.obj is _command_class("unguarded_report")
    ]


class TestTheReport:
    def test_one_warning_per_unguarded_spec_in_registry_order(self) -> None:
        command = _command_class("unguarded_report")
        expected = [
            Warning(
                unguarded_message(
                    UnguardedSpec(name, UnguardedReason.UNRESTRICTED), OWN + "report"
                ),
                hint=HINT,
                obj=command,
                id="django_service_specs.W001",
            )
            for name in ("open_service", "open_twice", "open_subclass")
        ]
        assert _own_w001(check_unguarded_specs(None)) == expected

    def test_a_command_that_is_no_spec_command_is_not_read(self) -> None:
        # Its class carries the same open registry as the report's, so reading
        # it would add three more W001s naming it.
        plain = _command_class("unguarded_plain")
        assert [m for m in check_unguarded_specs(None) if m.obj is plain] == []

    def test_an_empty_registry_reports_nothing(self) -> None:
        empty = _command_class("unguarded_empty")
        assert [m for m in check_unguarded_specs(None) if m.obj is empty] == []

    def test_never_an_error(self) -> None:
        assert all(not message.is_serious() for message in _own(check_unguarded_specs(None)))


class TestACommandThatDoesNotLoad:
    """Skipped and reported, because without this app nothing loads it at check time."""

    def _w003(self, name: str) -> list[str]:
        return [
            message.msg
            for message in check_unguarded_specs(None)
            if message.id == "django_service_specs.W003" and f"'{name}'" in message.msg
        ]

    def test_an_import_error_is_reported_with_its_cause(self) -> None:
        assert self._w003("unguarded_broken_import") == [
            "The command 'unguarded_broken_import' from tests.commands_app could not be set up, "
            "so its specs were not checked: RuntimeError: this command module cannot be imported"
        ]

    def test_a_constructor_error_is_reported_with_its_cause(self) -> None:
        assert self._w003("unguarded_broken_init") == [
            "The command 'unguarded_broken_init' from tests.commands_app could not be set up, "
            "so its specs were not checked: ValueError: this command cannot be constructed"
        ]

    def test_a_parser_that_cannot_be_built_is_reported_with_its_cause(self) -> None:
        # The command constructs, so only building its parser finds the clash
        # between a parameter and the option the command owns.
        [message] = self._w003("unguarded_bad_parser")
        assert message.startswith(
            "The command 'unguarded_bad_parser' from tests.commands_app could not be set up, "
            "so its specs were not checked: ImproperlyConfigured: "
        )
        assert "--as-user" in message

    def test_a_spec_command_naming_no_registry_is_reported(self) -> None:
        # Only that it is reported: how a ``SpecCommand`` with no registry
        # fails - reading it, constructing it, declaring it - is the command's
        # to decide, and each is caught by the same walk.
        [message] = self._w003("unguarded_no_registry")
        assert message.startswith(
            "The command 'unguarded_no_registry' from tests.commands_app could not be set up, "
            "so its specs were not checked: "
        )

    def test_the_warning_says_how_to_see_the_traceback(self) -> None:
        [message] = [
            m
            for m in check_unguarded_specs(None)
            if m.id == "django_service_specs.W003" and "'unguarded_broken_import'" in m.msg
        ]
        assert message.hint == (
            "Run manage.py unguarded_broken_import to see the traceback. Until it loads, "
            "the specs it serves are not checked."
        )
        assert message.level == Warning("").level

    def test_the_rest_of_the_project_is_still_checked(self) -> None:
        # A broken module sorted before the report's must not end the walk.
        assert len(_own_w001(check_unguarded_specs(None))) == 3


class TestAppConfigs:
    """``manage.py check <app_label>`` checks the commands of the apps it names."""

    def test_an_app_not_named_has_its_commands_skipped(self) -> None:
        assert _own(check_unguarded_specs([apps.get_app_config("auth")])) == []

    def test_the_app_named_has_its_commands_checked(self) -> None:
        named = check_unguarded_specs([apps.get_app_config("commands_app")])
        assert len(_own_w001(named)) == 3


class TestDjangoSOwnCommands:
    """Never a ``SpecCommand``, and importing all of them costs more than the rest of the walk."""

    def test_django_s_own_commands_are_not_loaded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        loaded: list[str] = []

        def recording(app_name: str, name: str) -> object:
            loaded.append(app_name)
            return load_command_class(app_name, name)

        monkeypatch.setattr("django_service_specs.checks.load_command_class", recording)
        check_unguarded_specs(None)
        assert APP in loaded
        assert "django.core" not in loaded

    def test_a_project_command_under_a_core_name_is_walked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # ``get_commands`` maps an overridden name to the app overriding it, so
        # the walk skips by app, never by name.
        monkeypatch.setattr("django_service_specs.checks.get_commands", lambda: {"shell": APP})
        monkeypatch.setattr(
            "django_service_specs.checks.load_command_class",
            lambda app_name, name: load_command_class(app_name, "unguarded_report"),
        )
        assert [m.msg.split(" authorizes")[0] for m in check_unguarded_specs(None)] == [
            "'open_service' in manage.py shell",
            "'open_twice' in manage.py shell",
            "'open_subclass' in manage.py shell",
        ]


class TestThroughTheCheckCommand:
    """Scoped to the commands app: another test app's models fail a project-wide check here."""

    def test_call_command_check_runs_it(self) -> None:
        err = io.StringIO()
        call_command("check", "commands_app", stderr=err)
        assert "(django_service_specs.W001) 'open_service' in manage.py unguarded_report" in (
            err.getvalue()
        )

    @override_settings(SILENCED_SYSTEM_CHECKS=["django_service_specs.W001"])
    def test_silencing_w001_keeps_w003(self) -> None:
        err = io.StringIO()
        call_command("check", "commands_app", stderr=err)
        assert "in manage.py unguarded_report" not in err.getvalue()
        assert "(django_service_specs.W003) The command 'unguarded_broken_import'" in (
            err.getvalue()
        )


class TestCallCommand:
    def test_skips_it_for_every_command_but_check(self) -> None:
        err = io.StringIO()
        call_command("unguarded_plain", stderr=err)
        assert "manage.py unguarded_report" not in err.getvalue()

    def test_runs_it_when_a_command_is_told_not_to_skip(self) -> None:
        # The same command with checks on reports, so the absence above is the
        # skip and not a command that never reaches the check. A project-wide
        # check fails on another test app's models where Pillow is missing,
        # and the warnings ride in the error then.
        err = io.StringIO()
        try:
            call_command("unguarded_plain", skip_checks=False, stderr=err)
        except SystemCheckError as failed:
            printed = str(failed)
        else:
            printed = err.getvalue()
        assert "'open_service' in manage.py unguarded_report" in printed


class TestTheDjangoInternalsTheWalkReads:
    """Neither function is documented API: these fail first if Django reshapes them."""

    def test_get_commands_maps_each_command_name_to_its_app_name(self) -> None:
        commands = get_commands()
        assert commands["unguarded_report"] == APP
        assert commands["check"] == "django.core"

    def test_load_command_class_returns_an_instance(self) -> None:
        loaded = load_command_class(APP, "unguarded_report")
        assert type(loaded) is _command_class("unguarded_report")

    def test_load_command_class_lets_an_import_error_propagate(self) -> None:
        with pytest.raises(RuntimeError, match="cannot be imported"):
            load_command_class(APP, "unguarded_broken_import")


def _probe(installed: list[str], body: str) -> subprocess.CompletedProcess[str]:
    probe = f"""
import django
from django.conf import settings
settings.configure(
    INSTALLED_APPS={installed!r},
    SECRET_KEY="probe",
    DATABASES={{"default": {{"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}}},
)
{body}
"""
    return subprocess.run(
        [sys.executable, "-c", probe], cwd=REPO_ROOT, capture_output=True, text=True
    )


BASE_APPS = ["django.contrib.contenttypes", "django.contrib.auth", APP]
CHECK = """
import io
django.setup()
from django.core.management import call_command
err = io.StringIO()
call_command("check", stderr=err)
print(err.getvalue())
"""


class TestTheAppIsTheOptIn:
    """A fresh interpreter each: the check registry is process-wide, and this one has the app."""

    def test_listing_the_app_registers_the_check(self) -> None:
        completed = _probe([*BASE_APPS, "django_service_specs"], CHECK)
        assert completed.returncode == 0, completed.stderr
        assert "'open_service' in manage.py unguarded_report" in completed.stdout

    def test_a_project_not_listing_it_gets_no_check(self) -> None:
        completed = _probe(BASE_APPS, CHECK)
        assert completed.returncode == 0, completed.stderr
        assert "django_service_specs." not in completed.stdout

    def test_a_manage_py_command_runs_it_before_its_own_handle(self) -> None:
        # The command line, unlike ``call_command``, does not skip system
        # checks, so a command keeping ``requires_system_checks`` prints the
        # report to stderr on every run.
        completed = _probe(
            [*BASE_APPS, "django_service_specs"],
            """
from django.core.management import execute_from_command_line
execute_from_command_line(["manage.py", "unguarded_plain"])
""",
        )
        assert completed.returncode == 0, completed.stderr
        assert "(django_service_specs.W001) 'open_service' in manage.py unguarded_report" in (
            completed.stderr
        )
