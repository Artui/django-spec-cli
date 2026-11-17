from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from functools import partial
from typing import Any, ClassVar

from django_service_specs import (
    DispatchError,
    DispatchResult,
    InvalidArguments,
    OutputPage,
    PoolSeeds,
    RegisteredSpec,
    ServiceError,
    SpecRegistry,
    coerce_flat,
    kernel_spec,
    paginate_output,
    present,
    row_links,
)
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Static
from textual.worker import Worker, WorkerFailed

from django_spec_cli.argv.describe_parameters import describe_parameters
from django_spec_cli.argv.utils import call_context, sendable, spec_summary
from django_spec_cli.render.refusal_text import refusal_text
from django_spec_cli.render.utils import TableColumn, table_cell, table_columns
from django_spec_cli.tui.actions_screen import ActionsScreen
from django_spec_cli.tui.parameter_fields import ParameterFields
from django_spec_cli.tui.row_screen import RowScreen
from django_spec_cli.tui.spec_form_screen import SpecFormScreen


class ChangelistScreen(Screen[None]):
    """A list selector's rows a page at a time, as the admin's changelist shows them.

    Cells read as the command's table; the filter bar sends reads; ``a`` lists a row's actions."""

    page_size: ClassVar[int | None] = None

    DEFAULT_CSS = """
    ChangelistScreen ParameterFields { max-height: 12; }
    ChangelistScreen #refusal { color: $error; }
    ChangelistScreen DataTable { height: 1fr; }
    """

    BINDINGS = [
        Binding("slash", "filter_bar", "Filter"),
        Binding("ctrl+s", "filter", "Apply filter", priority=True),
        Binding("n", "page(1)", "Next page"),
        Binding("p", "page(-1)", "Previous page"),
        Binding("r", "reload", "Reload"),
        Binding("a", "actions", "Actions"),
        Binding("escape", "back", "Back"),
    ]

    def __init__(
        self,
        subcommand: str,
        entry: RegisteredSpec,
        *,
        entries: Mapping[str, RegisteredSpec],
        refusals: Mapping[str, str],
        pool_seeds: PoolSeeds,
        command: str,
        call: Callable[..., Worker[Any]],
    ) -> None:
        super().__init__()
        self.subcommand = subcommand
        self.entry = entry
        self.entries = dict(entries)
        self.refusals = dict(refusals)
        self.spec = kernel_spec(entry.spec)
        self.rows: list[Any] = []
        self.page = 1
        self.arguments: dict[str, Any] = {}
        self._call = call
        self._command = command
        self._pool_seeds = pool_seeds
        self._registry = SpecRegistry(self.entries.values())
        self._subcommands = {held.name: name for name, held in self.entries.items()}
        self._parameters = sendable(self.spec, pool_seeds, call_context())

    def compose(self) -> ComposeResult:
        yield Header()
        summary = spec_summary(self.spec, self.entry.name)
        yield Static(Text.assemble((self.subcommand, "bold"), "  ", summary))
        yield ParameterFields(describe_parameters(self._parameters))
        yield Static(id="refusal")
        yield Static(id="status")
        yield DataTable(cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(DataTable).focus()
        self._load(self.arguments, 1)

    def action_filter_bar(self) -> None:
        fields = self.query_one(ParameterFields)
        if fields.descriptors:
            self.query_one(f"#field-{fields.descriptors[0].name}").focus()

    @on(Input.Submitted)
    def action_filter(self) -> None:
        self._say("#refusal", "")
        fields = self.query_one(ParameterFields)
        fields.show_refusals({})
        try:
            arguments = coerce_flat(
                self.spec.parameters(call_context=call_context()), fields.values()
            )
        except InvalidArguments as error:
            self._refused(error)
            return
        self._load(arguments, 1)

    def action_page(self, step: int) -> None:
        self._load(self.arguments, self.page + step)

    def action_reload(self) -> None:
        self._load(self.arguments, self.page)

    def action_back(self) -> None:
        table = self.query_one(DataTable)
        if self.focused is not table:
            table.focus()
            return
        self.app.pop_screen()

    def action_actions(self) -> None:
        if not self.rows:
            self.notify("No row to act on.")
            return
        row = self.rows[self.query_one(DataTable).cursor_row]
        links = row_links(self.entry.spec, row, registry=self._registry)
        if not links:
            self.notify("This row has no actions.")
            return
        listed = ActionsScreen(
            links, subcommands=self._subcommands, refusals=self.refusals, title=self.subcommand
        )
        self.app.push_screen(listed, partial(self._act, links))

    def _act(self, links: Mapping[str, Mapping[str, Any]], chosen: str | None) -> None:
        if chosen is None:
            return
        # The registered entry, never ``links[...]["spec"]``: ``name_of`` matches a displaced spec.
        subcommand = self._subcommands[links[chosen]["name"]]
        form = SpecFormScreen(
            subcommand,
            self.entries[subcommand],
            pool_seeds=self._pool_seeds,
            command=self._command,
            call=self._call,
            bound=links[chosen]["arguments"],
            on_success=self.action_reload,
        )
        self.app.push_screen(form)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row = self.rows[int(str(event.row_key.value))]
        self.app.push_screen(RowScreen(row, title=self.subcommand))

    def _load(self, arguments: Mapping[str, Any], page: int) -> None:
        self.run_worker(self._run(arguments, page), exclusive=True)

    async def _run(self, arguments: Mapping[str, Any], page: int) -> None:
        try:
            shown = await self._call(self.entry, arguments, partial(self._paged, page)).wait()
        except WorkerFailed as failed:
            if not isinstance(failed.error, DispatchError | ServiceError):
                raise failed.error from failed
            self._refused(failed.error)
            return
        self.arguments = dict(arguments)
        self._show(shown)

    def _paged(self, page: int, result: DispatchResult) -> OutputPage:
        """The page asked for, its rows presented; run in the dispatch's thread."""
        served = paginate_output(result.value, page=page, limit=self.page_size)
        return replace(served, items=present(self.entry.spec, replace(result, value=served.items)))

    def _show(self, page: OutputPage) -> None:
        self.rows = list(page.items)
        self.page = page.page
        self._say("#refusal", "")
        self.query_one(ParameterFields).show_refusals({})
        self._say("#status", f"Page {page.page} of {page.total_pages}, {page.total} in all")
        table = self.query_one(DataTable)
        table.clear(columns=True)
        columns = table_columns(self.rows, self.spec.output())
        for column in columns:
            table.add_column(Text(column.header), key=column.name)
        for index, row in enumerate(self.rows):
            table.add_row(*(_cell(row, column) for column in columns), key=str(index))

    def _refused(self, error: DispatchError | ServiceError) -> None:
        if not isinstance(error, InvalidArguments):
            self._say("#refusal", refusal_text(error))
            return
        rest = self.query_one(ParameterFields).show_refusals(error.detail)
        self._say("#refusal", "\n".join([str(error.message), *rest]))

    def _say(self, where: str, text: str) -> None:
        # ``Text``, never ``str``: a refusal or a value is no markup.
        self.query_one(where, Static).update(Text(text))


def _cell(row: Mapping[str, Any], column: TableColumn) -> Text:
    shown = table_cell(row.get(column.name), column.choices)
    return Text(shown, justify="right" if column.right else "left")
