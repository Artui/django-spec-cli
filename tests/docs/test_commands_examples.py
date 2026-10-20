"""The command line page's examples, run from argv as ``manage.py`` runs them.

``docs/commands.md`` includes its command classes from
``docs/examples/commands.py`` and shows runs in ``console`` blocks. Every
``$ python manage.py notes ...`` line there is run here through the example's
``Command``, from argv, and what it prints - stdout and stderr, as a terminal
shows them - must be the lines printed under it, and its exit status the
number an ``echo $?`` after it shows. So the page cannot show an option, an
output or an exit code the command does not have.
"""

from __future__ import annotations

import io
import re
import shlex
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from django_service_specs.commands.report.unguarded_message import unguarded_message
from django_service_specs.registry.unguarded_spec import UnguardedSpec
from django_service_specs.types.unguarded_reason import UnguardedReason
from docs.examples import commands
from tests.dispatch_app.models import Note

pytestmark = pytest.mark.django_db

PAGE = Path(__file__).resolve().parents[2] / "docs" / "commands.md"
PROMPT = "$ python manage.py notes "


def _runs() -> list[tuple[str, list[str], int]]:
    """Each command line the page shows: its argv, the lines printed under it, its exit status.

    A run with no ``echo $?`` after it is shown succeeding, so its status is 0.
    """
    runs: list[tuple[str, list[str], int]] = []
    for block in re.findall(r"```console\n(.*?)```", PAGE.read_text(), re.S):
        shown = iter(block.splitlines())
        for line in shown:
            if line == "$ echo $?":
                argv, printed, _ = runs[-1]
                runs[-1] = (argv, printed, int(next(shown)))
            elif line.startswith("$ "):
                assert line.startswith(PROMPT), line
                runs.append((line.removeprefix(PROMPT), [], 0))
            else:
                runs[-1][1].append(line)
    return runs


RUNS = _runs()


@pytest.fixture
def world(django_user_model: Any) -> None:
    """The page's world: user 1 is ada, user 2 is grace, and ada owns notes 1 and 2."""
    ada = django_user_model.objects.create_user(pk=1, username="ada")
    django_user_model.objects.create_user(pk=2, username="grace")
    Note.objects.create(pk=1, owner=ada, title="Draft")
    Note.objects.create(pk=2, owner=ada, title="Shopping")


@pytest.fixture(autouse=True)
def _keep_the_test_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    # run_from_argv closes every connection when it ends, which would close
    # the one this test's transaction is on.
    monkeypatch.setattr("django.db.connections.close_all", lambda: None)


def test_the_page_shows_runs_of_every_outcome_it_documents() -> None:
    # A regex that stopped matching would leave every run below unchecked.
    assert len(RUNS) >= 8
    assert {status for _, _, status in RUNS} >= {0, 3, 4, 6}


@pytest.mark.parametrize(("argv", "printed", "status"), RUNS, ids=[r[0] for r in RUNS])
@pytest.mark.usefixtures("world")
def test_a_run_prints_and_exits_as_the_page_shows(
    capsys: pytest.CaptureFixture[str], argv: str, printed: list[str], status: int
) -> None:
    # A run on the page changes the world only when it is shown succeeding,
    # and the page reads top to bottom, so every earlier write runs first.
    for earlier, _, earlier_status in RUNS[: RUNS.index((argv, printed, status))]:
        if earlier_status == 0 and earlier.startswith("rename-note"):
            _run_from_argv(earlier)
    capsys.readouterr()
    assert _run_from_argv(argv) == status
    out, err = capsys.readouterr()
    assert (out + err).splitlines() == printed


def _run_from_argv(argv: str) -> int:
    # ``--skip-checks``: this suite's project-wide check fails on another test
    # app's models, and the page's runs show no warnings.
    command = commands.Command()
    try:
        command.run_from_argv(["manage.py", "notes", "--skip-checks", *shlex.split(argv)])
    except SystemExit as exit:
        return int(exit.code or 0)
    return 0


def test_the_explain_line_is_the_sentence_the_report_writes() -> None:
    expected = unguarded_message(UnguardedSpec("whoami", UnguardedReason.UNRESTRICTED), "notes")
    assert expected in PAGE.read_text().splitlines()


@pytest.mark.usefixtures("world")
def test_the_username_lookup_runs_as_the_user_it_names() -> None:
    out = io.StringIO()
    call_command(commands.ByUsername(), "whoami", "--as-user", "grace", stdout=out)
    assert out.getvalue() == '"grace"\n'
    with pytest.raises(CommandError) as caught:
        call_command(commands.ByUsername(), "whoami", "--as-user", "nobody")
    assert (caught.value.returncode, str(caught.value)) == (5, "No user named 'nobody'.")


@pytest.mark.usefixtures("world")
def test_whoami_is_the_user_named(capsys: pytest.CaptureFixture[str]) -> None:
    assert _run_from_argv("whoami --as-user 1") == 0
    assert capsys.readouterr().out == '"ada"\n'
