from __future__ import annotations

import io
from collections.abc import Callable, Mapping
from typing import Any

from django_service_specs import (
    DispatchError,
    DispatchResult,
    InvalidArguments,
    PoolSeeds,
    RegisteredSpec,
    SelectorSpec,
    ServiceError,
    coerce_flat,
    file_output,
    kernel_spec,
    present,
)
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Select, Static, Switch, TextArea
from textual.worker import Worker, WorkerFailed

from django_spec_cli.argv.describe_parameters import describe_parameters
from django_spec_cli.argv.utils import call_context, sendable, spec_summary
from django_spec_cli.render.refusal_text import refusal_text
from django_spec_cli.render.render_result import render_result
from django_spec_cli.tui.parameter_fields import ParameterFields


class SpecFormScreen(Screen[None]):
    """One spec's parameters as a form, run with ``ctrl+s``, as the admin's change form saves.

    A write runs on a second ``ctrl+s``; a spec whose result is a file is named, never run."""

    DEFAULT_CSS = """
    SpecFormScreen #refusal { color: $error; }
    SpecFormScreen #prompt { color: $warning; }
    """

    BINDINGS = [
        Binding("ctrl+s", "run", "Run", priority=True),
        Binding("escape", "back", "Back"),
    ]

    def __init__(
        self,
        subcommand: str,
        entry: RegisteredSpec,
        *,
        pool_seeds: PoolSeeds,
        command: str,
        call: Callable[..., Worker[Any]],
    ) -> None:
        super().__init__()
        self.subcommand = subcommand
        self.entry = entry
        self.spec = kernel_spec(entry.spec)
        self.writes = not isinstance(self.spec, SelectorSpec)
        self.file = file_output(self.spec) is not None
        self.armed = False
        self._command = command
        self._call = call
        self._parameters = sendable(self.spec, pool_seeds, call_context())

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            summary = spec_summary(self.spec, self.entry.name)
            yield Static(Text.assemble((self.subcommand, "bold"), "  ", summary))
            if self.file:
                yield Static(Text(self._file_notice()), id="file")
            else:
                yield ParameterFields(describe_parameters(self._parameters))
            yield Static(id="prompt")
            yield Static(id="refusal")
            yield Static(id="result")
        yield Footer()

    def _file_notice(self) -> str:
        line = f"{self._command} {self.subcommand} --as-user USER --output-file PATH"
        return f"This spec makes a file, which this screen does not write. Run: {line}"

    def action_run(self) -> None:
        if self.file:
            return
        self._say("#refusal", "")
        self._say("#result", "")
        fields = self.query_one(ParameterFields)
        fields.show_refusals({})
        context = call_context()
        try:
            arguments = coerce_flat(self.spec.parameters(call_context=context), fields.values())
        except InvalidArguments as error:
            self._disarm()
            self._refused(error)
            return
        # Halves held by test_it_runs_on_one_key_..., test_one_ctrl_s_runs_nothing_...
        if self.writes and not self.armed:
            self.armed = True
            self._say("#prompt", f"{self.subcommand} writes: ctrl+s again runs it, esc cancels.")
            return
        self._disarm()
        self.run_worker(self._run(arguments), exclusive=True)

    async def _run(self, arguments: Mapping[str, Any]) -> None:
        try:
            shown = await self._call(self.entry, arguments, self._shown).wait()
        except WorkerFailed as failed:
            if not isinstance(failed.error, DispatchError | ServiceError):
                raise failed.error from failed
            self._refused(failed.error)
            return
        self._say("#result", shown)

    def _shown(self, result: DispatchResult) -> str:
        """The result as the command's table spells it; run in the dispatch's thread."""
        if result.kind == "not_found":
            return "Not found."
        presented = present(self.entry.spec, result)
        if presented is None:
            return "Done."
        out = io.StringIO()
        render_result(presented, self.spec.output(), out, table=True)
        return out.getvalue().rstrip("\n")

    def _refused(self, error: DispatchError | ServiceError) -> None:
        if not isinstance(error, InvalidArguments):
            self._say("#refusal", refusal_text(error))
            return
        rest = self.query_one(ParameterFields).show_refusals(error.detail)
        self._say("#refusal", "\n".join([str(error.message), *rest]))

    def _say(self, where: str, text: str) -> None:
        # ``Text``, never ``str``: a refusal or a value is no markup.
        self.query_one(where, Static).update(Text(text))

    def _disarm(self) -> None:
        self.armed = False
        self._say("#prompt", "")

    @on(Input.Changed)
    @on(Switch.Changed)
    @on(Select.Changed)
    @on(TextArea.Changed)
    def _edited(self) -> None:
        self._disarm()

    def action_back(self) -> None:
        if self.armed:
            self._disarm()
            return
        self.app.pop_screen()
