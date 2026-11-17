from __future__ import annotations

from collections.abc import Callable, Mapping
from functools import partial
from typing import Any, TypeVar

from django.db import connections
from django_service_specs import DispatchResult, PoolSeeds, RegisteredSpec, dispatch
from textual.app import App
from textual.binding import Binding
from textual.worker import Worker

from django_spec_cli.argv.utils import call_context
from django_spec_cli.tui.specs_screen import SpecsScreen

T = TypeVar("T")


class SpecTui(App[None]):
    """The terminal screens ``manage.py <command> --tui --as-user USER`` opens over a registry.

    Every call goes through ``dispatch`` as ``principal``, in a thread off Textual's event loop."""

    BINDINGS = [Binding("q", "quit", "Quit")]

    def __init__(
        self,
        *,
        entries: Mapping[str, RegisteredSpec],
        refusals: Mapping[str, str],
        principal: Any,
        pool_seeds: PoolSeeds,
        command_label: str,
    ) -> None:
        super().__init__()
        self.entries = dict(entries)
        self.refusals = dict(refusals)
        self.principal = principal
        self.pool_seeds = pool_seeds
        self.title = f"manage.py {command_label}"

    def on_mount(self) -> None:
        self.push_screen(SpecsScreen(self.entries, self.refusals))

    def on_specs_screen_chosen(self, message: SpecsScreen.Chosen) -> None:
        self.notify(f"{message.subcommand} has no screen yet.", markup=False)

    def call_off_loop(
        self,
        entry: RegisteredSpec,
        arguments: Mapping[str, Any],
        then: Callable[[DispatchResult], T],
    ) -> Worker[T]:
        """Dispatch ``entry`` as the principal in a worker thread, and ``then`` its result there."""
        work = partial(self._call, entry, arguments, then)
        return self.run_worker(work, thread=True, exit_on_error=False)

    def _call(
        self,
        entry: RegisteredSpec,
        arguments: Mapping[str, Any],
        then: Callable[[DispatchResult], T],
    ) -> T:
        # The ORM refuses a sync call on the loop; this thread's connection closes with its work.
        try:
            result = dispatch(
                entry.spec,
                principal=self.principal,
                arguments=arguments,
                pool_seeds=self.pool_seeds,
                call_context=call_context(),
            )
            return then(result)
        finally:
            connections.close_all()
