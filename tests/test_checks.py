from __future__ import annotations

import importlib
import io
from typing import Any

import pytest
from django.apps import apps
from django.core.checks import CheckMessage, Warning
from django.core.management import call_command, get_commands, load_command_class
from django.core.management.base import SystemCheckError
from django.test import override_settings
from django_service_specs import (
    DEFAULT_POOL_SEEDS,
    Parameter,
    Parameters,
    PoolSeeds,
    ServiceSpec,
    SpecRegistry,
    UnguardedReason,
    UnguardedSpec,
    Unrestricted,
    ValidationContext,
    Validator,
    call_transport,
)

from django_spec_cli.checks import check_unguarded_specs
from django_spec_cli.report.unguarded_message import unguarded_message
from django_spec_cli.spec_command import SpecCommand
from tests.commands_app.unguarded_registries import StaffOnly
from tests.utils import run_project

APP = "tests.commands_app"
OWN = "unguarded_"
HINT = (
    "Declare a PermissionCheck that refuses someone in the spec's permissions, or add "
    "'django_spec_cli.W001' to SILENCED_SYSTEM_CHECKS if the spec is meant to be open."
)


def _command_class(name: str) -> type:
    return importlib.import_module(f"{APP}.management.commands.{name}").Command


def _own(messages: list[CheckMessage]) -> list[CheckMessage]:
    return [
        message
        for message in messages
        if message.id is not None
        and message.id.startswith("django_spec_cli.")
        and f"'{OWN}" in message.msg
    ]


def _own_w001(messages: list[CheckMessage]) -> list[CheckMessage]:
    return [
        message
        for message in messages
        if message.id == "django_spec_cli.W001"
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
                id="django_spec_cli.W001",
            )
            for name in ("open_service", "open_twice", "open_subclass")
        ]
        assert _own_w001(check_unguarded_specs(None)) == expected

    @pytest.mark.parametrize(
        "name",
        [
            # Its open registry would add three more W001s naming it.
            "unguarded_plain",
            "unguarded_empty",
        ],
        ids=["no-spec-command", "empty-registry"],
    )
    def test_a_command_with_nothing_to_report_reports_nothing(self, name: str) -> None:
        command = _command_class(name)
        assert [m for m in check_unguarded_specs(None) if m.obj is command] == []

    def test_never_an_error(self) -> None:
        assert all(not message.is_serious() for message in _own(check_unguarded_specs(None)))


class TestACommandThatDoesNotLoad:
    """Skipped and reported, because without this app nothing loads it at check time."""

    def _w003(self, name: str) -> list[CheckMessage]:
        return [
            message
            for message in check_unguarded_specs(None)
            if message.id == "django_spec_cli.W003" and f"'{name}'" in message.msg
        ]

    @pytest.mark.parametrize(
        ("name", "cause"),
        [
            ("unguarded_broken_import", "RuntimeError: this command module cannot be imported"),
            ("unguarded_broken_init", "ValueError: this command cannot be constructed"),
        ],
        ids=["import", "constructor"],
    )
    def test_an_import_or_constructor_error_is_reported_with_its_cause(
        self, name: str, cause: str
    ) -> None:
        assert [message.msg for message in self._w003(name)] == [
            f"The command {name!r} from tests.commands_app could not be set up, "
            f"so its specs were not checked: {cause}"
        ]

    def test_a_parser_that_cannot_be_built_is_reported_with_its_cause(self) -> None:
        # Only building the parser finds a parameter clashing with an option the command owns.
        [message] = [m.msg for m in self._w003("unguarded_bad_parser")]
        assert message.startswith(
            "The command 'unguarded_bad_parser' from tests.commands_app could not be set up, "
            "so its specs were not checked: ImproperlyConfigured: "
        )
        assert "--as-user" in message

    def test_a_spec_command_naming_no_registry_is_reported(self) -> None:
        # Only that it is reported; how a SpecCommand with no registry fails is for the command.
        [message] = self._w003("unguarded_no_registry")
        assert message.msg.startswith(
            "The command 'unguarded_no_registry' from tests.commands_app could not be set up, "
            "so its specs were not checked: "
        )

    def test_the_warning_says_how_to_see_the_traceback(self) -> None:
        [message] = self._w003("unguarded_broken_import")
        assert message.hint == (
            "Run manage.py unguarded_broken_import to see the traceback. Until it loads, "
            "the specs it serves are not checked."
        )
        assert message.level == Warning("").level

    def test_the_rest_of_the_project_is_still_checked(self) -> None:
        # A broken module sorted before the report's must not end the walk.
        assert len(_own_w001(check_unguarded_specs(None))) == 3


def _needs_project(*, project: int) -> dict[str, int]:
    return {"project": project}


def _echo(**pool: object) -> object:
    return pool


def _greet(*, tenant: str) -> str:
    return f"hello {tenant}"


def _project_spec(*, required: bool) -> ServiceSpec:
    """A read ``project`` beside a ``kwargs`` provider that takes it by name, with no default."""
    return ServiceSpec(
        service=_echo,
        permissions=[StaffOnly()],
        reads=Parameters.of(Parameter("project", "integer", required=required)),
        kwargs=_needs_project,
    )


class TestADeclarationTheKernelRefuses:
    """``check_seeds``, under the command's own ``pool_seeds``, over every spec it serves."""

    REFUSED = (
        "'optional_project' in manage.py seeded cannot run as declared, and a run of it is "
        "refused: ServiceSpec.kwargs requires the keyword(s) ['project'], declared as optional "
        "reads that nothing else fills, so a call leaving one out fails with the provider's "
        "own TypeError. Declare the read required, or give the keyword a default."
    )

    def _walk(
        self,
        monkeypatch: pytest.MonkeyPatch,
        registry: SpecRegistry,
        pool_seeds: PoolSeeds = DEFAULT_POOL_SEEDS,
    ) -> tuple[type, list[CheckMessage]]:
        command = type("Command", (SpecCommand,), {"registry": registry, "pool_seeds": pool_seeds})
        monkeypatch.setattr("django_spec_cli.checks.get_commands", lambda: {"seeded": APP})
        monkeypatch.setattr(
            "django_spec_cli.checks.load_command_class", lambda app_name, name: command()
        )
        return command, check_unguarded_specs(None)

    def test_an_optional_read_a_provider_requires_is_reported(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = SpecRegistry()
        registry.register("optional_project", _project_spec(required=False))
        command, messages = self._walk(monkeypatch, registry)
        assert [m for m in messages if m.id == "django_spec_cli.W004"] == [
            Warning(
                self.REFUSED,
                hint=(
                    "Change the declaration as the message says. Until then a run of the spec "
                    "is refused, whether or not django_spec_cli.W004 is silenced."
                ),
                obj=command,
                id="django_spec_cli.W004",
            )
        ]

    def test_a_spec_it_accepts_is_not_reported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        registry = SpecRegistry()
        registry.register("required_project", _project_spec(required=True))
        _, messages = self._walk(monkeypatch, registry)
        assert messages == []

    def test_one_warning_per_refused_spec_beside_the_command_s_other_reports(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Refusing one spec loses neither the W001 of an open spec nor the command to a W003.
        registry = SpecRegistry()
        registry.register("optional_project", _project_spec(required=False))
        registry.register("required_project", _project_spec(required=True))
        registry.register("open", ServiceSpec(service=_echo, permissions=[Unrestricted()]))
        registry.register("unseeded", ServiceSpec(service=_greet, permissions=[StaffOnly()]))
        _, messages = self._walk(monkeypatch, registry)
        assert [(m.id, m.msg.split(" ")[0]) for m in messages] == [
            ("django_spec_cli.W001", "'open'"),
            ("django_spec_cli.W004", "'optional_project'"),
            ("django_spec_cli.W004", "'unseeded'"),
        ]
        assert not any(message.is_serious() for message in messages)

    def test_it_reads_the_command_s_pool_seeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # tenant is filled by nothing under the stock seeds, and by the seed the command registers.
        registry = SpecRegistry()
        registry.register("greet", ServiceSpec(service=_greet, permissions=[StaffOnly()]))
        _, unseeded = self._walk(monkeypatch, registry)
        assert [m.id for m in unseeded] == ["django_spec_cli.W004"]
        assert "['tenant']" in unseeded[0].msg
        seeds = DEFAULT_POOL_SEEDS.extend(tenant=lambda: "acme")
        _, seeded = self._walk(monkeypatch, registry, pool_seeds=seeds)
        assert seeded == []


class _SeedNamedUnderCli(Validator):
    """Declares ``user``, a name dispatch seeds itself, only when the transport is ``cli``."""

    def parameters(self, *, call_context: Any = None) -> Parameters:
        declared = [Parameter("n", "integer", required=False)]
        if call_transport(call_context) == "cli":
            declared.append(Parameter("user", "string", required=False))
        return Parameters.of(*declared)

    def validate(self, arguments: Any, context: ValidationContext) -> dict[str, Any]:
        return dict(arguments)


class TestADeclarationOnlyTheCliStampedReadRefuses:
    """The read the parser makes under the stamped dict, which ``check_seeds`` never sees."""

    def _walk(
        self, monkeypatch: pytest.MonkeyPatch, registry: SpecRegistry
    ) -> tuple[type, list[CheckMessage]]:
        command = type("Command", (SpecCommand,), {"registry": registry})
        monkeypatch.setattr("django_spec_cli.checks.get_commands", lambda: {"seeded": APP})
        monkeypatch.setattr(
            "django_spec_cli.checks.load_command_class", lambda app_name, name: command()
        )
        return command, check_unguarded_specs(None)

    def test_the_spec_is_reported_as_w004_naming_it_and_the_command_is_no_w003(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = SpecRegistry()
        registry.register(
            "bad",
            ServiceSpec(service=_echo, permissions=[StaffOnly()], validator=_SeedNamedUnderCli()),
        )
        registry.register("good", ServiceSpec(service=_echo, permissions=[StaffOnly()]))
        command, messages = self._walk(monkeypatch, registry)
        assert [(m.id, m.obj) for m in messages] == [("django_spec_cli.W004", command)]
        assert messages[0].msg.startswith(
            "'bad' in manage.py seeded cannot run as declared, and a run of it is refused: "
            "ServiceSpec.validator declares the parameter(s) ['user'], which dispatch seeds itself."
        )

    def test_a_command_overriding_add_arguments_without_super_is_still_checked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class Bare(SpecCommand):
            registry = SpecRegistry()

            def add_arguments(self, parser: Any) -> None: ...

        registry = SpecRegistry()
        registry.register("open", ServiceSpec(service=_echo, permissions=[Unrestricted()]))
        Bare.registry = registry
        monkeypatch.setattr("django_spec_cli.checks.get_commands", lambda: {"bare": APP})
        monkeypatch.setattr("django_spec_cli.checks.load_command_class", lambda *_: Bare())
        assert [m.id for m in check_unguarded_specs(None)] == ["django_spec_cli.W001"]

    def test_a_spec_both_reads_refuse_is_reported_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        both = ServiceSpec(
            service=_echo,
            permissions=[StaffOnly()],
            validator=_SeedNamedUnderCli(),
            reads=Parameters.of(Parameter("project", "integer", required=False)),
            kwargs=_needs_project,
        )
        registry = SpecRegistry()
        registry.register("both", both)
        _, messages = self._walk(monkeypatch, registry)
        assert [m.id for m in messages] == ["django_spec_cli.W004"]
        assert "requires the keyword(s) ['project']" in messages[0].msg


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

        monkeypatch.setattr("django_spec_cli.checks.load_command_class", recording)
        check_unguarded_specs(None)
        assert APP in loaded
        assert "django.core" not in loaded

    def test_a_project_command_under_a_core_name_is_walked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # get_commands maps an overridden name to the overriding app, so the walk skips by app.
        monkeypatch.setattr("django_spec_cli.checks.get_commands", lambda: {"shell": APP})
        monkeypatch.setattr(
            "django_spec_cli.checks.load_command_class",
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
        assert "(django_spec_cli.W001) 'open_service' in manage.py unguarded_report" in (
            err.getvalue()
        )

    @override_settings(SILENCED_SYSTEM_CHECKS=["django_spec_cli.W001"])
    def test_silencing_w001_keeps_w003(self) -> None:
        err = io.StringIO()
        call_command("check", "commands_app", stderr=err)
        assert "in manage.py unguarded_report" not in err.getvalue()
        assert "(django_spec_cli.W003) The command 'unguarded_broken_import'" in (err.getvalue())


class TestCallCommand:
    def test_skips_it_for_every_command_but_check(self) -> None:
        err = io.StringIO()
        call_command("unguarded_plain", stderr=err)
        assert "manage.py unguarded_report" not in err.getvalue()

    def test_runs_it_when_a_command_is_told_not_to_skip(self) -> None:
        # With checks on the same command reports, so the absence above is the skip, not a miss.
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
        completed = run_project([*BASE_APPS, "django_spec_cli"], CHECK)
        assert completed.returncode == 0, completed.stderr
        assert "'open_service' in manage.py unguarded_report" in completed.stdout

    def test_a_project_not_listing_it_gets_no_check(self) -> None:
        completed = run_project(BASE_APPS, CHECK)
        assert completed.returncode == 0, completed.stderr
        assert "django_spec_cli." not in completed.stdout

    def test_a_manage_py_command_runs_it_before_its_own_handle(self) -> None:
        # The command line runs system checks, unlike call_command, so the report prints each run.
        completed = run_project(
            [*BASE_APPS, "django_spec_cli"],
            """
from django.core.management import execute_from_command_line
execute_from_command_line(["manage.py", "unguarded_plain"])
""",
        )
        assert completed.returncode == 0, completed.stderr
        assert "(django_spec_cli.W001) 'open_service' in manage.py unguarded_report" in (
            completed.stderr
        )

    def test_the_kernel_s_app_registers_no_check_of_its_own(self) -> None:
        # The kernel keeps an AppConfig but registers nothing: the checks live in this package.
        completed = run_project([*BASE_APPS, "django_service_specs"], CHECK)
        assert completed.returncode == 0, completed.stderr
        assert "django_service_specs." not in completed.stdout
