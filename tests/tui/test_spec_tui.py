from __future__ import annotations

import threading
from typing import Any

import pytest
from django.core.exceptions import SynchronousOnlyOperation
from django_service_specs import DispatchResult, InvalidArguments, dispatch, present
from textual.worker import WorkerFailed

from django_spec_cli.tui.specs_screen import SpecsScreen
from tests.commands_app.management.commands import notes
from tests.dispatch_app.models import Note
from tests.tui.utils import app_over, entries_of

LIST_NOTES = entries_of(notes.registry)["list-notes"]


@pytest.fixture
def owner(django_user_model: Any) -> Any:
    owner = django_user_model.objects.create_user(username="ada")
    Note.objects.create(owner=owner, title="written by the test")
    return owner


@pytest.mark.django_db(transaction=True)
class TestOffTheLoop:
    async def test_a_dispatch_runs_in_a_thread_and_reads_the_row_the_test_wrote(
        self, owner: Any
    ) -> None:
        threads: list[int] = []

        def then(result: DispatchResult) -> Any:
            threads.append(threading.get_ident())
            return present(LIST_NOTES.spec, result)

        app = app_over(notes.registry, owner)
        async with app.run_test():
            rows = await app.call_off_loop(LIST_NOTES, {}, then).wait()
        assert [row["title"] for row in rows] == ["written by the test"]
        assert threads != [threading.get_ident()]

    async def test_the_same_dispatch_on_the_loop_is_refused_by_the_orm(self, owner: Any) -> None:
        # What the thread is for: the loop is no place for a sync ORM call.
        with pytest.raises(SynchronousOnlyOperation):
            present(LIST_NOTES.spec, dispatch(LIST_NOTES.spec, principal=owner, arguments={}))

    async def test_a_refusal_reaches_whoever_waits(self, owner: Any) -> None:
        app = app_over(notes.registry, owner)
        async with app.run_test():
            worker = app.call_off_loop(LIST_NOTES, {"nope": 1}, lambda result: result)
            with pytest.raises(WorkerFailed) as caught:
                await worker.wait()
        assert isinstance(caught.value.error, InvalidArguments)


class TestTheApp:
    async def test_it_opens_on_the_specs_screen_titled_for_the_command(self) -> None:
        app = app_over(notes.registry)
        async with app.run_test():
            assert isinstance(app.screen, SpecsScreen)
            assert app.title == "manage.py notes"

    async def test_q_quits(self) -> None:
        app = app_over(notes.registry)
        async with app.run_test() as pilot:
            await pilot.press("q")
        assert app.return_code == 0

    async def test_choosing_a_spec_names_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        told: list[str] = []
        app = app_over(notes.registry)
        monkeypatch.setattr(app, "notify", lambda message, **_: told.append(message))
        async with app.run_test() as pilot:
            await pilot.press("enter")
        assert told == ["rename-note has no screen yet."]
