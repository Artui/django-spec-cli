from __future__ import annotations

import argparse
import inspect
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, BinaryIO, TextIO, cast

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils.translation import gettext
from django_service_specs import (
    DEFAULT_POOL_SEEDS,
    DispatchError,
    FilePresenter,
    Parameters,
    PoolSeeds,
    PrincipalUnavailable,
    RegisteredSpec,
    ServiceError,
    SpecRegistry,
    check_seeds,
    coerce_flat,
    dispatch,
    file_output,
    kernel_spec,
    present,
    resolve_principal,
    unguarded_specs,
)

from django_spec_cli.argv.add_spec_arguments import add_spec_arguments
from django_spec_cli.argv.describe_parameters import describe_parameters
from django_spec_cli.argv.parsed_arguments import parsed_arguments
from django_spec_cli.argv.utils import call_context, sendable, spec_summary
from django_spec_cli.exit_code_for import exit_code_for
from django_spec_cli.render.refusal_text import refusal_text
from django_spec_cli.render.render_result import render_result
from django_spec_cli.render.wants_table import wants_table
from django_spec_cli.render.write_file import write_file
from django_spec_cli.report.unguarded_message import unguarded_message
from django_spec_cli.report.utils import refused_message
from django_spec_cli.types.exit_code import ExitCode

_OWN_OPTIONS = frozenset({"--as-user", "--json", "--table"})
"""The options every subcommand owns, which no spec parameter may map to."""

_OUTPUT_FILE = "--output-file"


class SpecCommand(BaseCommand):
    """A management command serving every spec in a registry, one subcommand each.

    Declared by subclassing, in the project's own ``management/commands/``
    module, which names the registry::

        class Command(SpecCommand):
            registry = notes_registry

    The registry is the subclass's to name, so one project can expose two
    registries under two command names. It is read when the parser is built,
    and a command naming none is refused then, as ``ImproperlyConfigured``.
    ``pool_seeds`` names the seeds the specs' callables are resolved with, as
    ``pool_seeds`` on django-spec-html's ``SpecView`` does, for a registry
    whose callables read one.

    It is run as ``manage.py <command> <spec> --as-user USER [--json|--table]
    [--option value ...]``, or ``manage.py <command> --explain``:

    - **One subcommand per registry entry**, named after the entry with each
      ``_`` shown as ``-``. Its options are the spec's parameters, as
      [`add_spec_arguments`][django_spec_cli.argv.add_spec_arguments.add_spec_arguments]
      spells them, as the input schema a transport advertises asks for them
      ([`spec_caller_input_schema`][django_service_specs.schema.spec_caller_input_schema.spec_caller_input_schema]
      under ``pool_seeds`` and the stamped ``call_context``): less any key the server
      fills, and required only where dispatch refuses leaving it out.
      No option is matched by a prefix: an abbreviation is refused rather
      than read as whichever option it begins.
    - **``--as-user`` is required.** Its value goes through
      [`resolve_as_user`][django_spec_cli.spec_command.SpecCommand.resolve_as_user],
      and the user it returns is the principal ``dispatch`` runs the spec
      for, with the permission checks enforced: the command passes no
      ``Grant``, and opens no transaction of its own.
    - The result goes through the spec's presenter and is written as a table
      or as JSON Lines: ``--table`` and ``--json`` choose, then the
      ``SPEC_CLI_OUTPUT`` setting, then whether stdout is a
      terminal ([`wants_table`][django_spec_cli.render.wants_table.wants_table]).
    - **A spec whose result is a file**, one
      [`file_output`][django_service_specs.schema.file_output.file_output]
      answers a ``FilePresenter`` for, writes its bytes instead
      ([`write_file`][django_spec_cli.render.write_file.write_file]): to
      ``--output-file PATH``, an option only its subcommand takes, or else to
      stdout's binary buffer when stdout is not a terminal. At a terminal
      without ``--output-file``, ``--table`` or ``--json``, a stdout that
      takes no bytes, or a ``PATH`` that is a directory or whose directory does
      not exist, the run is refused before the user is looked up or the spec
      is run, so nothing is written. The setting ``SPEC_CLI_OUTPUT`` is
      not read for it. The file's name goes to stderr, and is never a path.
      A file spec ``file_output`` refuses is refused as declared, below.
    - A refusal ends the run with a ``CommandError`` carrying its message and
      an [`ExitCode`][django_spec_cli.types.exit_code.ExitCode].
    - **A spec the kernel refuses as declared is never run.**
      [`check_seeds`][django_service_specs.dispatch.check_seeds.check_seeds],
      under ``pool_seeds``, is asked of the spec named before anything else,
      and its refusal is raised as ``ImproperlyConfigured``, as a command
      naming no registry is: a traceback and ``ExitCode.ERROR``, whatever
      the options sent. The command's other specs still run, and the system
      check reports the same spec as ``django_spec_cli.W004``. The same holds for a spec
      whose Validator declares, only to ``cli``, a parameter dispatch seeds
      itself: ``check_seeds`` is asked outside a call and never sees it, the
      read the parser makes under the stamped dict does, and the parser takes
      that refusal for its spec alone. Its subcommand takes no option and its
      ``--help`` gives the reason; a run raises it as above, and W004 reports
      it too
      (test_a_run_of_it_is_refused_with_the_kernel_s_reason_whatever_is_sent).
    - **``--tui --as-user USER``** opens the terminal screens over every spec,
      with the ``tui`` extra installed. ``tui_css`` names a Textual stylesheet
      they are styled with, a path read against the directory of the module
      declaring the command, as Textual reads an App's ``CSS_PATH``; one that
      is no file is refused as ``ImproperlyConfigured`` before anything opens.
    - ``--explain`` runs no spec: it lists the ones that authorize nothing,
      as the system check does.

    The command is a mistake-prevention and attribution surface, **never an
    authorization boundary**: whoever can run ``manage.py`` can run any code
    the project can, and names any user they like with ``--as-user``. What
    it guarantees is that a run is attributed to a user and checked against
    the permissions that user holds.

    Sync only: it dispatches with ``dispatch``, never ``adispatch``.
    """

    registry: SpecRegistry
    pool_seeds: PoolSeeds = DEFAULT_POOL_SEEDS
    tui_css: str | Path | None = None
    help = "Run one operation of a registry of specs, as the user --as-user names."

    _command_label: str
    _parser: CommandParser
    _entries: dict[str, RegisteredSpec]
    _refused_by_declaration: dict[str, ImproperlyConfigured]
    _files: dict[str, FilePresenter]

    def create_parser(self, prog_name: str, subcommand: str, **kwargs: Any) -> CommandParser:
        """Django's parser, with this command's options added and no option read by its prefix."""
        self._command_label = subcommand
        self._refused_by_declaration = {}
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        parser.allow_abbrev = False
        self._parser = parser
        return parser

    def add_arguments(self, parser: CommandParser) -> None:
        """``--explain``, then one subcommand per registry entry, each with its spec's options.

        Every subcommand is built here, on every run: one spec's options are
        a handful of ``add_argument`` calls, and building them eagerly is
        what lets ``--help`` list every spec.

        Raises:
            ImproperlyConfigured: the class names no ``SpecRegistry``; two
                entries are one subcommand, ``a_b`` and ``a-b``; or a spec
                parameter maps to an option the command owns - ``--as-user``,
                ``--json``, ``--table``, or one of Django's own, such as
                ``--settings``, which ``manage.py`` reads from anywhere on
                the line.
        """
        registry = getattr(self, "registry", None)
        if not isinstance(registry, SpecRegistry):
            cls = type(self)
            raise ImproperlyConfigured(
                f"{cls.__module__}.{cls.__qualname__} names no registry: declare "
                f"registry = SpecRegistry(...) on the class (got {registry!r})."
            )
        parser.add_argument(
            "--explain",
            action="store_true",
            help="List the specs this command serves that authorize nothing, and run none.",
        )
        reserved = _OWN_OPTIONS | frozenset(parser._option_string_actions)
        parser.add_argument(
            "--tui",
            action="store_true",
            help="Open the terminal screens over every spec, as the user --as-user names. "
            "Needs the tui extra.",
        )
        parser.add_argument(
            "--as-user",
            dest="tui_as_user",
            metavar="USER",
            help="With --tui: the user every spec on the screens runs as.",
        )
        subparsers = parser.add_subparsers(dest="spec_name", metavar="spec", title="specs")
        self._entries = {}
        self._files = {}
        for entry in registry:
            name = entry.name.replace("_", "-")
            if name in self._entries:
                raise ImproperlyConfigured(
                    f"The specs {self._entries[name].name!r} and {entry.name!r} are both the "
                    f"subcommand {name!r}; register one of them under another name."
                )
            self._entries[name] = entry
            spec = kernel_spec(entry.spec)
            summary = spec_summary(spec, entry.name)
            try:
                parameters = sendable(spec, self.pool_seeds, call_context())
                file = file_output(spec)
            except ImproperlyConfigured as error:
                self._refused_by_declaration[entry.name] = error
                _add_refused_subparser(
                    subparsers,
                    name,
                    summary,
                    refused_message(entry.name, self._command_label, error),
                )
                continue
            subparser = subparsers.add_parser(
                name,
                help=summary.replace("%", "%%"),
                description=summary,
                epilog=_unsendable(parameters),
                allow_abbrev=False,
            )
            subparser.add_argument(
                "--as-user",
                dest="as_user",
                required=True,
                metavar="USER",
                help="The user the operation runs as, and is checked and recorded for.",
            )
            # A file spec keeps both unlisted and ungrouped: 3.10's usage asserts on a hidden group.
            formats = subparser if file is not None else subparser.add_mutually_exclusive_group()
            formats.add_argument(
                "--json",
                dest="output_format",
                action="store_const",
                const="json",
                help="Write the result as JSON Lines, one row per line."
                if file is None
                else argparse.SUPPRESS,
            )
            formats.add_argument(
                "--table",
                dest="output_format",
                action="store_const",
                const="table",
                help="Write the result as a table." if file is None else argparse.SUPPRESS,
            )
            if file is None:
                add_spec_arguments(subparser, parameters, reserved=reserved)
                continue
            self._files[entry.name] = file
            subparser.add_argument(
                _OUTPUT_FILE,
                dest="output_file",
                metavar="PATH",
                help=f"Write the {file.content_type.replace('%', '%%')} file this makes to PATH, "
                "replacing what is there. Without it the bytes go to stdout, which must not be a "
                "terminal.",
            )
            add_spec_arguments(subparser, parameters, reserved=reserved | {_OUTPUT_FILE})

    def resolve_as_user(self, value: str) -> Any:
        """The user ``--as-user VALUE`` names, or ``PrincipalUnavailable``.

        By primary key, through
        [`resolve_principal`][django_service_specs.authorization.resolve_principal.resolve_principal],
        which refuses a missing row, a malformed key and a deactivated
        account. A project whose runbooks name people by username or email
        overrides this method with that lookup.

        The contract is: return an authenticated user, or raise
        [`PrincipalUnavailable`][django_service_specs.authorization.principal_unavailable.PrincipalUnavailable],
        which ends the run with ``ExitCode.PRINCIPAL_UNAVAILABLE``. Anything
        else an override raises is a bug in the lookup, and propagates. An
        override need not refuse a deactivated user itself: ``dispatch``
        refuses one whatever the lookup returns. A lookup answering ``None``
        or an anonymous user is refused the same way, by the command. There is
        no fallback to an anonymous user and no user of the command's own.
        """
        return resolve_principal(value)

    def handle(self, *args: Any, **options: Any) -> None:
        name = options["spec_name"]
        if options["tui"]:
            self._tui(name, options)
            return
        if options["explain"]:
            if name is not None:
                self._parser.error("--explain runs no spec; leave out the spec name.")
            self._explain()
            return
        if name is None:
            self._parser.error(
                f"manage.py {self._command_label} serves no spec: its registry is empty."
                if not self._entries
                else "name a spec to run, or pass --explain. --help lists the specs."
            )
        entry = self._entries[name]
        refusal = self._declaration_refusal(entry)
        if refusal is not None:
            raise ImproperlyConfigured(
                refused_message(entry.name, self._command_label, refusal)
            ) from refusal
        spec = kernel_spec(entry.spec)
        context = call_context()
        parameters = spec.parameters(call_context=context)
        raw = parsed_arguments(argparse.Namespace(**options), parameters)
        stdout = cast("TextIO", self.stdout)
        file = self._files.get(entry.name)
        if file is None:
            table = wants_table(stdout, requested=options["output_format"])
        else:
            sink = self._file_sink(name, options, stdout)
        try:
            principal = self._principal(options["as_user"])
            result = dispatch(
                entry.spec,
                principal=principal,
                arguments=coerce_flat(parameters, raw),
                pool_seeds=self.pool_seeds,
                call_context=context,
            )
        except (DispatchError, ServiceError) as error:
            raise CommandError(refusal_text(error), returncode=int(exit_code_for(error))) from error
        if result.kind == "not_found":
            raise CommandError(gettext("Not found."), returncode=int(ExitCode.NOT_FOUND))
        if file is None:
            render_result(present(entry.spec, result), spec.output(), stdout, table=table)
            return
        written = write_file(present(entry.spec, result), sink)
        if written is not None:
            self.stderr.write(written, style_func=str)

    def _declaration_refusal(self, entry: RegisteredSpec) -> ImproperlyConfigured | None:
        """Why the kernel refuses ``entry`` as declared, read as a run reads it, or ``None``."""
        try:
            check_seeds(entry.spec, pool_seeds=self.pool_seeds)
        except ImproperlyConfigured as error:
            return error
        return self._refused_by_declaration.get(entry.name)

    def _principal(self, as_user: str) -> Any:
        principal = self.resolve_as_user(as_user)
        # A lookup answering ``None`` is refused: ``filter(...).first()`` answers it for a typo.
        if principal is None or not getattr(principal, "is_authenticated", False):
            raise PrincipalUnavailable(f"The user {as_user!r} resolved to nobody who can sign in.")
        return principal

    def _tui_css(self) -> Path | None:
        if self.tui_css is None:
            return None
        path = Path(inspect.getfile(type(self))).parent / self.tui_css
        if not path.is_file():
            cls = type(self)
            raise ImproperlyConfigured(
                f"{cls.__module__}.{cls.__qualname__}.tui_css is {str(self.tui_css)!r}, and "
                f"{str(path)!r} is no file."
            )
        return path

    def _tui(self, name: str | None, options: Mapping[str, Any]) -> None:
        if name is not None or options["explain"]:
            self._parser.error("--tui runs no spec from the command line; leave out the spec name.")
        if options["tui_as_user"] is None:
            self._parser.error("--tui needs --as-user USER, the user every spec there runs as.")
        try:
            # Textual is the ``[tui]`` extra's, so only ``--tui`` imports it (rule 4).
            from django_spec_cli.tui.spec_tui import SpecTui
        except ImportError as error:
            if (error.name or "").partition(".")[0] != "textual":
                raise
            raise CommandError(
                "--tui needs the tui extra: pip install 'django-spec-cli[tui]'."
            ) from error
        css = self._tui_css()
        try:
            principal = self._principal(options["tui_as_user"])
        except PrincipalUnavailable as error:
            raise CommandError(refusal_text(error), returncode=int(exit_code_for(error))) from error
        refusals = {
            entry.name: refused_message(entry.name, self._command_label, refusal)
            for entry in self._entries.values()
            if (refusal := self._declaration_refusal(entry)) is not None
        }
        SpecTui(
            entries=self._entries,
            refusals=refusals,
            principal=principal,
            pool_seeds=self.pool_seeds,
            command_label=self._command_label,
            css_path=css,
        ).run()

    def _file_sink(self, name: str, options: Mapping[str, Any], stdout: TextIO) -> Path | BinaryIO:
        """Where a file spec's bytes go, or a usage error before anything runs."""
        if options["output_format"] is not None:
            self._parser.error(
                f"{name} writes a file, so --{options['output_format']} does not apply: "
                f"pass {_OUTPUT_FILE} PATH, or send stdout to a pipe or a file."
            )
        if options["output_file"] is not None:
            path = Path(options["output_file"])
            if path.is_dir() or not path.parent.is_dir():
                self._parser.error(
                    f"{_OUTPUT_FILE} {str(path)!r} is a directory, or its directory does not exist."
                )
            return path
        if stdout.isatty():
            self._parser.error(
                f"{name} writes a file, and stdout is a terminal: pass {_OUTPUT_FILE} PATH, "
                "or send stdout to a pipe or a file."
            )
        buffer = getattr(stdout, "buffer", None)
        if buffer is None:
            self._parser.error(
                f"{name} writes a file, and stdout takes no bytes: pass {_OUTPUT_FILE} PATH."
            )
        return cast("BinaryIO", buffer)

    def _explain(self) -> None:
        label = self._command_label
        if not self._entries:
            self.stdout.write(f"manage.py {label} serves no spec: its registry is empty.")
            return
        found = unguarded_specs(self.registry)
        if not found:
            self.stdout.write(
                f"Every spec manage.py {label} serves declares a permission check other than "
                "Unrestricted."
            )
        for unguarded in found:
            self.stdout.write(unguarded_message(unguarded, label))


def _add_refused_subparser(subparsers: Any, name: str, summary: str, message: str) -> None:
    """The subcommand of a refused spec, under the stamped dict: its reason, and no option."""
    subparser = subparsers.add_parser(
        name,
        help=summary.replace("%", "%%"),
        description=summary,
        epilog=message.replace("%", "%%") if "%(prog)" in message else message,
        usage="%(prog)s [arguments ...]",
        allow_abbrev=False,
    )
    reads_help = subparser.parse_known_args

    def take_everything(
        args: Sequence[str], namespace: argparse.Namespace | None = None
    ) -> tuple[argparse.Namespace, list[str]]:
        # ``_SubParsersAction`` hands a list and a ``None`` namespace.
        if {"-h", "--help"} & set(args):
            return reads_help(args, namespace)
        return argparse.Namespace(), []

    subparser.parse_known_args = take_everything


def _unsendable(parameters: Parameters) -> str | None:
    """The epilog naming the parameters no option can send, or ``None`` when there are none."""
    names = [d.name for d in describe_parameters(parameters) if not d.argv]
    return f"Takes arguments a command line cannot send: {', '.join(names)}." if names else None
