"""``SpecCommand``, run as a project runs it: by name through ``call_command``, and from argv.

Exit codes are asserted as the integers a script branches on, not through
``ExitCode``, so the table the docs publish is what is held here.
"""

from __future__ import annotations

import functools
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, TypedDict

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from django_service_specs.authorization.principal_unavailable import PrincipalUnavailable
from django_service_specs.authorization.unrestricted import Unrestricted
from django_service_specs.commands.render.render_json_lines import render_json_lines
from django_service_specs.commands.report.unguarded_message import unguarded_message
from django_service_specs.commands.report.unguarded_spec import UnguardedSpec
from django_service_specs.commands.spec_command import SpecCommand
from django_service_specs.dispatch.dispatch import dispatch
from django_service_specs.dispatch.present import present
from django_service_specs.parameters.parameters import Parameter, Parameters
from django_service_specs.pool.pool_seeds import DEFAULT_POOL_SEEDS
from django_service_specs.registry.spec_registry import SpecRegistry
from django_service_specs.specs.service_spec import ServiceSpec
from django_service_specs.types.unguarded_reason import UnguardedReason
from tests.commands_app.management.commands import notes
from tests.dispatch_app.models import Note

pytestmark = pytest.mark.django_db

REPO_ROOT = Path(__file__).resolve().parents[2]


# --- helpers -------------------------------------------------------------------------------------


def run(*argv: str, command: str | SpecCommand = "notes") -> str:
    """``argv`` through ``call_command``; what the command wrote to stdout."""
    out = io.StringIO()
    call_command(command, *argv, stdout=out, stderr=io.StringIO())
    return out.getvalue()


def refused(*argv: str, command: str | SpecCommand = "notes") -> CommandError:
    with pytest.raises(CommandError) as caught:
        run(*argv, command=command)
    return caught.value


def lines(out: str) -> list[Any]:
    return [json.loads(line) for line in out.splitlines()]


def help_of(capsys: pytest.CaptureFixture[str], *argv: str, command: SpecCommand) -> str:
    """What ``--help`` prints for ``argv``, which argparse writes to ``sys.stdout`` and exits."""
    parser = command.create_parser("manage.py", "notes")
    with pytest.raises(SystemExit):
        parser.parse_args([*argv, "--help"])
    return capsys.readouterr().out


def command_over(registry: SpecRegistry, **attributes: Any) -> SpecCommand:
    """A ``SpecCommand`` over ``registry``, declared as a project declares one."""
    return type("Command", (SpecCommand,), {"registry": registry, **attributes})()


def echo_spec(*parameters: Parameter, **declared: Any) -> ServiceSpec:
    """An open spec whose service returns the arguments it was sent, and nothing from the pool."""
    reads = Parameters.of(*parameters)

    def echo(**pool: Any) -> dict[str, Any]:
        return {name: pool[name] for name in reads.names() if name in pool}

    return ServiceSpec(service=echo, permissions=[Unrestricted()], reads=reads, **declared)


class Filled(TypedDict):
    project: int


def fill_project(**_: Any) -> Filled:
    return {"project": 1}


@pytest.fixture
def owner(django_user_model: Any) -> Any:
    return django_user_model.objects.create_user(username="ada")


@pytest.fixture
def other(django_user_model: Any) -> Any:
    return django_user_model.objects.create_user(username="grace")


@pytest.fixture
def note(owner: Any) -> Note:
    return Note.objects.create(owner=owner, title="draft")


# --- declaring -----------------------------------------------------------------------------------


class TestDeclaring:
    def test_a_command_naming_no_registry_is_refused_when_its_parser_is_built(self) -> None:
        with pytest.raises(ImproperlyConfigured, match=r"unguarded_no_registry\.Command") as caught:
            call_command("unguarded_no_registry")
        assert "names no registry" in str(caught.value)

    def test_a_registry_that_is_no_spec_registry_is_refused(self) -> None:
        registry: Any = {"ping": notes.ping_spec}
        command = command_over(registry)
        with pytest.raises(ImproperlyConfigured, match="names no registry"):
            command.create_parser("manage.py", "notes")

    def test_each_entry_is_a_subcommand_with_underscores_shown_as_hyphens(
        self, owner: Any, note: Note
    ) -> None:
        out = run("rename-note", "--as-user", str(owner.pk), "--pk", str(note.pk), "--title", "x")
        assert lines(out) == [{"id": note.pk, "title": "x"}]
        assert "invalid choice: 'rename_note'" in str(
            refused("rename_note", "--as-user", str(owner.pk))
        )

    def test_two_names_that_read_alike_are_refused(self) -> None:
        registry = SpecRegistry()
        registry.register("a_b", notes.ping_spec)
        registry.register("a-b", notes.ping_spec)
        with pytest.raises(ImproperlyConfigured, match="'a_b' and 'a-b'.*'a-b'"):
            command_over(registry).create_parser("manage.py", "notes")

    @pytest.mark.parametrize(
        "name", ["as_user", "json", "table", "settings", "pythonpath", "verbosity", "traceback"]
    )
    def test_a_parameter_on_an_option_the_command_owns_is_refused(self, name: str) -> None:
        registry = SpecRegistry()
        registry.register("echo", echo_spec(Parameter(name, "string")))
        with pytest.raises(ImproperlyConfigured, match="is the command's own"):
            command_over(registry).create_parser("manage.py", "notes")

    def test_a_spec_declared_by_a_source_is_read_as_the_spec_it_compiles_to(
        self, owner: Any, note: Note
    ) -> None:
        out = run("my-notes", "--as-user", str(owner.pk), "--search", "dra")
        assert lines(out) == [{"id": note.pk, "title": "draft"}]


# --- running -------------------------------------------------------------------------------------


class TestRunning:
    def test_a_write_changes_the_row_and_prints_what_it_presents(
        self, owner: Any, note: Note
    ) -> None:
        out = run(
            "rename-note", "--as-user", str(owner.pk), "--pk", str(note.pk), "--title", "final"
        )
        note.refresh_from_db()
        assert note.title == "final"
        assert lines(out) == [{"id": note.pk, "title": "final"}]

    def test_a_read_prints_one_line_per_row_for_its_principal_only(
        self, owner: Any, other: Any, note: Note
    ) -> None:
        mine = Note.objects.create(owner=owner, title="second")
        Note.objects.create(owner=other, title="theirs")
        out = run("list-notes", "--as-user", str(owner.pk))
        assert lines(out) == [{"id": note.pk, "title": "draft"}, {"id": mine.pk, "title": "second"}]

    def test_a_one_spec_registry_is_one_subcommand(self, owner: Any, note: Note) -> None:
        command = command_over(notes.registry.subset("rename_note"))
        out = run(
            "rename-note",
            "--as-user",
            str(owner.pk),
            "--pk",
            str(note.pk),
            "--title",
            "x",
            command=command,
        )
        assert lines(out) == [{"id": note.pk, "title": "x"}]

    def test_a_boolean_is_a_flag_pair(self, owner: Any) -> None:
        base = ("schedule", "--as-user", str(owner.pk), "--due-at", "2026-10-14T09:30:00Z")
        assert lines(run(*base, "--urgent"))[0]["urgent"] is True
        assert lines(run(*base, "--no-urgent"))[0]["urgent"] is False
        assert lines(run(*base))[0]["urgent"] is False

    def test_an_array_is_a_repeated_option(self, owner: Any) -> None:
        out = run(
            "schedule",
            "--as-user",
            str(owner.pk),
            "--due-at",
            "2026-10-14T09:30:00Z",
            "--tags",
            "a",
            "--tags",
            "b c",
        )
        assert lines(out)[0]["tags"] == ["a", "b c"]

    def test_an_offset_date_time_keeps_its_offset(self, owner: Any) -> None:
        out = run("schedule", "--as-user", str(owner.pk), "--due-at", "2026-10-14T09:30:00+02:00")
        [row] = lines(out)
        assert row["due_at"] == "2026-10-14T09:30:00+02:00"
        assert row["offset"] == "2:00:00"

    def test_argv_dispatches_what_the_same_values_off_a_json_wire_dispatch(
        self, owner: Any
    ) -> None:
        out = run(
            "schedule",
            "--as-user",
            str(owner.pk),
            "--due-at",
            "2026-10-14T09:30:00+02:00",
            "--urgent",
            "--tags",
            "a",
            "--tags",
            "b",
            "--count",
            "3",
            "--json",
        )
        wire = {
            "due_at": "2026-10-14T09:30:00+02:00",
            "urgent": True,
            "tags": ["a", "b"],
            "count": 3,
        }
        result = dispatch(
            notes.schedule_spec, principal=owner, arguments=json.loads(json.dumps(wire))
        )
        expected = io.StringIO()
        render_json_lines([present(notes.schedule_spec, result)], expected)
        assert out == expected.getvalue()

    def test_a_service_returning_a_scalar_prints_its_json(self, owner: Any) -> None:
        assert run("ping", "--as-user", str(owner.pk)) == '"pong"\n'

    def test_a_service_returning_nothing_writes_nothing(self, owner: Any) -> None:
        def archive_all() -> None:
            return None

        registry = SpecRegistry()
        registry.register("archive", ServiceSpec(service=archive_all, permissions=[Unrestricted()]))
        assert run("archive", "--as-user", str(owner.pk), command=command_over(registry)) == ""

    def test_an_async_service_is_run_as_dispatch_runs_one(self, owner: Any) -> None:
        async def aping() -> str:
            return "pong"

        registry = SpecRegistry()
        registry.register("aping", ServiceSpec(service=aping, permissions=[Unrestricted()]))
        assert run("aping", "--as-user", str(owner.pk), command=command_over(registry)) == (
            '"pong"\n'
        )

    def test_an_error_nothing_maps_is_left_to_propagate(self, owner: Any) -> None:
        def broken() -> None:
            raise RuntimeError("a bug")

        registry = SpecRegistry()
        registry.register("broken", ServiceSpec(service=broken, permissions=[Unrestricted()]))
        with pytest.raises(RuntimeError, match="a bug"):
            run("broken", "--as-user", str(owner.pk), command=command_over(registry))


class TestSeeds:
    def _registry(self) -> SpecRegistry:
        def greet(*, tenant: str) -> str:
            return f"hello {tenant}"

        registry = SpecRegistry()
        registry.register("greet", ServiceSpec(service=greet, permissions=[Unrestricted()]))
        return registry

    def test_the_seeds_a_command_names_resolve_the_services_callables(self, owner: Any) -> None:
        # The HTTP entry points take ``pool_seeds``; a command over the same
        # registry has to be able to answer a callable that reads one.
        seeds = DEFAULT_POOL_SEEDS.extend(tenant=lambda: "acme")
        command = command_over(self._registry(), pool_seeds=seeds)
        assert run("greet", "--as-user", str(owner.pk), command=command) == '"hello acme"\n'

    def test_with_no_seeds_named_a_callable_reading_one_fails_as_dispatch_does(
        self, owner: Any
    ) -> None:
        # The default is the stock seeds, as ``dispatch``'s: a seed nobody
        # registered is the callable's own ``TypeError``, not a quiet default.
        with pytest.raises(TypeError, match="tenant"):
            run("greet", "--as-user", str(owner.pk), command=command_over(self._registry()))


class TestAbbreviation:
    """A prefix of an option is never read as the option, the command's own or a spec's."""

    @pytest.fixture
    def command(self) -> SpecCommand:
        registry = SpecRegistry()
        registry.register(
            "echo", echo_spec(Parameter("as_user_id", "integer"), Parameter("title", "string"))
        )
        return command_over(registry)

    def test_as_user_names_the_principal_and_never_the_parameter(
        self, command: SpecCommand, owner: Any, other: Any
    ) -> None:
        out = run("echo", "--as-user", str(other.pk), "--as-user-id", "7", command=command)
        assert lines(out) == [{"as_user_id": 7}]

    @pytest.mark.parametrize("prefix", ["--as-user-i", "--titl"])
    def test_a_prefix_of_a_spec_option_is_refused(
        self, command: SpecCommand, owner: Any, prefix: str
    ) -> None:
        error = refused("echo", "--as-user", str(owner.pk), prefix, "3", command=command)
        assert f"unrecognized arguments: {prefix} 3" in str(error)

    def test_a_prefix_of_the_command_s_own_option_is_refused(
        self, command: SpecCommand, owner: Any
    ) -> None:
        error = refused("echo", "--as-us", str(owner.pk), command=command)
        assert "the following arguments are required: --as-user" in str(error)

    def test_a_prefix_of_one_of_django_s_options_is_refused(self) -> None:
        # ``--expl`` would be ``--explain``, and ``--verb`` ``--verbosity``.
        assert "unrecognized arguments: --expl" in str(refused("--expl"))


class TestThePrincipal:
    def test_as_user_is_required(self) -> None:
        error = refused("ping")
        assert "the following arguments are required: --as-user" in str(error)

    def test_a_subclass_may_look_the_user_up_by_username(self, owner: Any) -> None:
        def resolve_as_user(self: SpecCommand, value: str) -> Any:
            try:
                return get_user_model().objects.get(username=value)
            except get_user_model().DoesNotExist:
                raise PrincipalUnavailable(f"No user {value!r}.") from None

        command = command_over(notes.registry, resolve_as_user=resolve_as_user)
        out = run("list-notes", "--as-user", "ada", command=command)
        assert lines(out) == []
        error = refused("list-notes", "--as-user", "nobody", command=command)
        assert (error.returncode, str(error)) == (5, "No user 'nobody'.")

    def test_a_deactivated_user_a_lookup_returns_is_refused_by_dispatch(self, owner: Any) -> None:
        owner.is_active = False
        owner.save()
        command = command_over(notes.registry, resolve_as_user=lambda self, value: owner)
        error = refused("ping", "--as-user", "ada", command=command)
        assert error.returncode == 5


class TestHelp:
    def test_a_percent_sign_in_a_docstring_is_help_text_and_not_a_format(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        def discount() -> None:
            """Take 10% off."""

        registry = SpecRegistry()
        registry.register("discount", ServiceSpec(service=discount, permissions=[Unrestricted()]))
        assert "Take 10% off. (write)" in help_of(capsys, command=command_over(registry))

    def test_each_subcommand_says_what_its_spec_s_callable_says_and_its_kind(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        text = help_of(capsys, command=notes.Command())
        assert "Give a note a new title. (write)" in text
        assert "list_notes (read)" in text

    def test_only_a_function_s_or_a_method_s_own_docstring_is_read(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        class Shelf:
            def tidy(self) -> None:
                """Put every note back in order."""

        registry = SpecRegistry()
        # A method's own docstring describes the operation; a ``partial``'s is
        # the class's, which describes ``partial``.
        registry.register("tidy", ServiceSpec(service=Shelf().tidy, permissions=[Unrestricted()]))
        registry.register(
            "later",
            ServiceSpec(service=functools.partial(notes.ping), permissions=[Unrestricted()]),
        )
        text = help_of(capsys, command=command_over(registry))
        assert "Put every note back in order. (write)" in text
        assert "later (write)" in text

    def test_a_partial_spec_requires_only_what_names_its_row(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        text = " ".join(help_of(capsys, "retitle", command=notes.Command()).split())
        assert "--pk INTEGER (required)" in text
        assert "--title STRING --archived" in text

    def test_a_spec_that_is_not_partial_marks_its_required_option(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        text = " ".join(help_of(capsys, "rename-note", command=notes.Command()).split())
        assert "--title STRING (required)" in text

    def test_a_parameter_argv_cannot_send_is_named_in_the_epilog(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        registry = SpecRegistry()
        registry.register("echo", echo_spec(Parameter("meta", "object"), Parameter("n", "integer")))
        text = help_of(capsys, "echo", command=command_over(registry))
        assert "--meta" not in text
        assert "Takes arguments a command line cannot send: meta." in text

    def test_a_key_the_server_fills_is_no_option(self, capsys: pytest.CaptureFixture[str]) -> None:
        spec = echo_spec(
            Parameter("project", "integer", required=True),
            Parameter("n", "integer"),
            kwargs=fill_project,
        )
        registry = SpecRegistry()
        registry.register("echo", spec)
        text = help_of(capsys, "echo", command=command_over(registry))
        assert "--project" not in text
        assert "--n INTEGER" in text


# --- output --------------------------------------------------------------------------------------


class TestOutput:
    @pytest.fixture
    def argv(self, owner: Any, note: Note) -> tuple[str, ...]:
        return ("list-notes", "--as-user", str(owner.pk))

    def test_a_buffer_gets_json_lines_by_default(self, argv: tuple[str, ...]) -> None:
        assert lines(run(*argv))[0]["title"] == "draft"

    def test_table_by_flag(self, argv: tuple[str, ...]) -> None:
        out = run(*argv, "--table")
        assert out.splitlines()[0].split() == ["id", "title"]

    @override_settings(SERVICE_SPECS_COMMAND_OUTPUT="table")
    def test_table_by_setting_and_json_by_flag_over_it(self, argv: tuple[str, ...]) -> None:
        assert run(*argv).splitlines()[0].split() == ["id", "title"]
        assert lines(run(*argv, "--json"))[0]["title"] == "draft"

    def test_json_and_table_are_exclusive(self, argv: tuple[str, ...]) -> None:
        assert "not allowed with argument" in str(refused(*argv, "--json", "--table"))


# --- refusals and exit codes ---------------------------------------------------------------------


class TestRefusals:
    def test_invalid_arguments_name_each_field(self, owner: Any, note: Note) -> None:
        error = refused("rename-note", "--as-user", str(owner.pk), "--pk", str(note.pk))
        assert error.returncode == 3
        assert str(error).splitlines()[1:] == ["title: This field is required."]

    def test_a_malformed_flat_value_is_invalid_arguments(self, owner: Any) -> None:
        error = refused("rename-note", "--as-user", str(owner.pk), "--pk", "x", "--title", "t")
        assert error.returncode == 3
        assert str(error).splitlines()[1].startswith("pk: ")

    def test_a_non_owner_is_not_permitted(self, other: Any, note: Note) -> None:
        error = refused(
            "rename-note", "--as-user", str(other.pk), "--pk", str(note.pk), "--title", "x"
        )
        assert (error.returncode, str(error)) == (4, "Only the note's owner may change it.")
        note.refresh_from_db()
        assert note.title == "draft"

    def test_a_deactivated_user_is_refused(self, owner: Any, note: Note) -> None:
        owner.is_active = False
        owner.save()
        error = refused(
            "rename-note", "--as-user", str(owner.pk), "--pk", str(note.pk), "--title", "x"
        )
        assert error.returncode == 5
        assert "deactivated" in str(error)

    def test_no_such_user_is_principal_unavailable(self) -> None:
        error = refused("ping", "--as-user", "999")
        assert (error.returncode, str(error)) == (5, "No principal with identifier '999'.")

    def test_a_lookup_answering_none_is_refused(self, owner: Any) -> None:
        # ``Unrestricted`` is the spec an unattributed run would succeed on.
        command = command_over(notes.registry, resolve_as_user=lambda self, value: None)
        error = refused("ping", "--as-user", "typo", command=command)
        assert error.returncode == 5
        assert "'typo'" in str(error)

    def test_a_lookup_answering_an_anonymous_user_is_refused(self) -> None:
        command = command_over(notes.registry, resolve_as_user=lambda self, value: AnonymousUser())
        assert refused("ping", "--as-user", "x", command=command).returncode == 5

    def test_a_setting_naming_no_format_is_refused_before_the_write(self, owner: Any) -> None:
        # Read after the run, it failed a rename that had already committed.
        note = Note.objects.create(owner=owner, title="draft")
        with (
            override_settings(SERVICE_SPECS_COMMAND_OUTPUT="TABLE"),
            pytest.raises(ImproperlyConfigured),
        ):
            run(
                "rename-note",
                "--as-user",
                str(owner.pk),
                "--pk",
                str(note.pk),
                "--title",
                "renamed",
            )
        note.refresh_from_db()
        assert note.title == "draft"

    def test_a_missing_row_is_not_found(self, owner: Any) -> None:
        error = refused("rename-note", "--as-user", str(owner.pk), "--pk", "999", "--title", "x")
        assert (error.returncode, str(error)) == (6, "Not found.")

    @pytest.mark.parametrize(
        ("kind", "code", "message"),
        [
            ("validation", 3, "The title is taken."),
            (
                "validation_map",
                3,
                "Service validation error.\nCheck the shelf.\ntitle: Too long.\n"
                "books.1: Missing.\nbooks.1.isbn: Malformed.",
            ),
            ("validation_list", 3, "Service validation error.\nFirst.\nSecond."),
            ("not_found", 6, "No such shelf."),
            ("conflict", 7, "Already archived."),
            ("unavailable", 7, "The note is archived. (code: archived)"),
            ("input", 8, "40 notes match. Confirm to proceed. Run it again with: --confirmed"),
            ("input_bare", 8, "Confirm to proceed."),
            ("other", 9, "The shelf is full."),
        ],
    )
    def test_a_service_s_refusal_is_its_exit_code(
        self, owner: Any, kind: str, code: int, message: str
    ) -> None:
        error = refused("refuse", "--as-user", str(owner.pk), "--kind", kind)
        assert (error.returncode, str(error)) == (code, message)


class TestUsage:
    def test_neither_a_spec_nor_explain_is_a_usage_error(self) -> None:
        error = refused()
        assert "name a spec to run, or pass --explain" in str(error)
        # Through call_command every parser error is Django's CommandError
        # with returncode 1; the command line's 2 is held by TestFromArgv.
        assert error.returncode == 1

    def test_explain_with_a_spec_is_a_usage_error(self, owner: Any) -> None:
        error = refused("--explain", "ping", "--as-user", str(owner.pk))
        assert "--explain runs no spec" in str(error)

    def test_an_empty_registry_is_a_usage_error_saying_so(self) -> None:
        assert "serves no spec" in str(refused(command=command_over(SpecRegistry())))


class TestExplain:
    def test_lists_every_spec_that_authorizes_nothing(self) -> None:
        expected = unguarded_message(UnguardedSpec("ping", UnguardedReason.UNRESTRICTED), "notes")
        assert run("--explain") == expected + "\n"

    def test_says_so_when_every_spec_is_guarded(self) -> None:
        command = command_over(notes.registry.subset("rename_note", "list_notes"))
        out = run("--explain", command=command)
        assert out.startswith("Every spec manage.py ")
        assert "declares a permission check" in out

    def test_an_empty_registry_serves_nothing_to_explain(self) -> None:
        assert "serves no spec" in run("--explain", command=command_over(SpecRegistry()))


# --- from argv, as manage.py runs it -------------------------------------------------------------


class TestFromArgv:
    """``run_from_argv``: a ``CommandError``'s message to stderr, its code to ``sys.exit``."""

    @pytest.fixture(autouse=True)
    def _keep_the_test_connection(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # run_from_argv closes every connection when it ends, which would close
        # the one this test's transaction is on.
        monkeypatch.setattr("django.db.connections.close_all", lambda: None)

    def argv_exit(
        self, capsys: pytest.CaptureFixture[str], *argv: str
    ) -> tuple[int | str | None, str, str]:
        with pytest.raises(SystemExit) as caught:
            notes.Command().run_from_argv(["manage.py", "notes", "--skip-checks", *argv])
        out, err = capsys.readouterr()
        return caught.value.code, out, err

    def test_success_exits_by_returning(
        self, capsys: pytest.CaptureFixture[str], owner: Any
    ) -> None:
        notes.Command().run_from_argv(
            ["manage.py", "notes", "--skip-checks", "ping", "--as-user", str(owner.pk)]
        )
        assert capsys.readouterr().out == '"pong"\n'

    @pytest.mark.parametrize(
        ("argv", "code"),
        [
            (("ping",), 2),
            ((), 2),
            (("--explain", "ping", "--as-user", "1"), 2),
            (("ping", "--as-user", "999"), 5),
            (("refuse", "--as-user", "{owner}", "--kind", "bogus"), 3),
            (("refuse", "--as-user", "{owner}", "--kind", "conflict"), 7),
            (("refuse", "--as-user", "{owner}", "--kind", "input"), 8),
            (("refuse", "--as-user", "{owner}", "--kind", "other"), 9),
            (("rename-note", "--as-user", "{owner}", "--pk", "999", "--title", "x"), 6),
        ],
    )
    def test_each_refusal_exits_with_its_code(
        self, capsys: pytest.CaptureFixture[str], owner: Any, argv: tuple[str, ...], code: int
    ) -> None:
        actual, out, err = self.argv_exit(capsys, *(a.format(owner=owner.pk) for a in argv))
        assert actual == code
        assert out == ""
        assert err

    def test_a_refusal_is_written_once_to_stderr(
        self, capsys: pytest.CaptureFixture[str], other: Any, note: Note
    ) -> None:
        code, _, err = self.argv_exit(
            capsys, "rename-note", "--as-user", str(other.pk), "--pk", str(note.pk), "--title", "x"
        )
        assert (code, err) == (4, "CommandError: Only the note's owner may change it.\n")

    def test_a_usage_error_prints_the_usage(self, capsys: pytest.CaptureFixture[str]) -> None:
        _, _, err = self.argv_exit(capsys, "ping")
        assert err.startswith("usage: manage.py notes ping")


def test_manage_py_exits_with_the_code_and_runs_the_system_check() -> None:
    """A real ``manage.py`` run in a fresh interpreter: system checks on, Django's own exit."""
    probe = """
import django
from django.conf import settings
settings.configure(
    INSTALLED_APPS=[
        "django.contrib.contenttypes", "django.contrib.auth", "django_service_specs",
        "tests.commands_app", "tests.dispatch_app",
    ],
    SECRET_KEY="probe",
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
)
django.setup()
from django.core.management import call_command, execute_from_command_line
call_command("migrate", verbosity=0, run_syncdb=True)
execute_from_command_line(["manage.py", "notes", "ping", "--as-user", "999"])
"""
    completed = subprocess.run(
        [sys.executable, "-c", probe], cwd=REPO_ROOT, capture_output=True, text=True
    )
    assert completed.returncode == 5, completed.stderr
    assert "(django_service_specs.W001) 'ping' in manage.py notes authorizes nothing" in (
        completed.stderr
    )
    assert completed.stderr.endswith("CommandError: No principal with identifier '999'.\n")
