from __future__ import annotations

import argparse
import inspect
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any, TextIO, cast

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils.translation import gettext
from django_service_specs import (
    DEFAULT_POOL_SEEDS,
    ActionUnavailable,
    AdditionalInputRequired,
    DispatchError,
    InvalidArguments,
    Parameters,
    PoolSeeds,
    PrincipalUnavailable,
    RegisteredSpec,
    SelectorSpec,
    ServiceError,
    ServiceSpec,
    ServiceValidationError,
    SpecRegistry,
    build_call_context,
    check_seeds,
    coerce_flat,
    dispatch,
    kernel_spec,
    present,
    refusal_messages,
    resolve_principal,
    spec_caller_input_schema,
    unguarded_specs,
)

from django_spec_cli.argv.add_spec_arguments import add_spec_arguments
from django_spec_cli.argv.describe_parameters import describe_parameters
from django_spec_cli.argv.parsed_arguments import parsed_arguments
from django_spec_cli.argv.utils import option_string
from django_spec_cli.exit_code_for import exit_code_for
from django_spec_cli.render.render_result import render_result
from django_spec_cli.render.wants_table import wants_table
from django_spec_cli.report.unguarded_message import unguarded_message
from django_spec_cli.report.utils import refused_message
from django_spec_cli.types.cli_transport import CLI_TRANSPORT
from django_spec_cli.types.exit_code import ExitCode

_OWN_OPTIONS = frozenset({"--as-user", "--json", "--table"})
"""The options every subcommand owns, which no spec parameter may map to."""


class SpecCommand(BaseCommand):
    """A management command serving every spec in a registry, one subcommand each."""

    registry: SpecRegistry
    pool_seeds: PoolSeeds = DEFAULT_POOL_SEEDS
    help = "Run one operation of a registry of specs, as the user --as-user names."

    _command_label: str
    _parser: CommandParser
    _entries: dict[str, RegisteredSpec]
    _refused_by_declaration: dict[str, ImproperlyConfigured]

    def create_parser(self, prog_name: str, subcommand: str, **kwargs: Any) -> CommandParser:
        """Django's parser, with this command's options added and no option read by its prefix."""
        self._command_label = subcommand
        self._refused_by_declaration = {}
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        parser.allow_abbrev = False
        self._parser = parser
        return parser

    def add_arguments(self, parser: CommandParser) -> None:
        """``--explain``, then one subcommand per registry entry, each with its spec's options."""
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
        subparsers = parser.add_subparsers(dest="spec_name", metavar="spec", title="specs")
        self._entries = {}
        for entry in registry:
            name = entry.name.replace("_", "-")
            if name in self._entries:
                raise ImproperlyConfigured(
                    f"The specs {self._entries[name].name!r} and {entry.name!r} are both the "
                    f"subcommand {name!r}; register one of them under another name."
                )
            self._entries[name] = entry
            spec = kernel_spec(entry.spec)
            summary = _summary(spec, entry.name)
            try:
                parameters = _sendable(spec, self.pool_seeds, _call_context())
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
            formats = subparser.add_mutually_exclusive_group()
            formats.add_argument(
                "--json",
                dest="output_format",
                action="store_const",
                const="json",
                help="Write the result as JSON Lines, one row per line.",
            )
            formats.add_argument(
                "--table",
                dest="output_format",
                action="store_const",
                const="table",
                help="Write the result as a table.",
            )
            add_spec_arguments(subparser, parameters, reserved=reserved)

    def resolve_as_user(self, value: str) -> Any:
        """The user ``--as-user VALUE`` names, or ``PrincipalUnavailable``."""
        return resolve_principal(value)

    def handle(self, *args: Any, **options: Any) -> None:
        name = options["spec_name"]
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
        try:
            check_seeds(entry.spec, pool_seeds=self.pool_seeds)
            declared = self._refused_by_declaration.get(entry.name)
            if declared is not None:
                raise declared
        except ImproperlyConfigured as error:
            raise ImproperlyConfigured(
                refused_message(entry.name, self._command_label, error)
            ) from error
        spec = kernel_spec(entry.spec)
        call_context = _call_context()
        parameters = spec.parameters(call_context=call_context)
        raw = parsed_arguments(argparse.Namespace(**options), parameters)
        stdout = cast("TextIO", self.stdout)
        table = wants_table(stdout, requested=options["output_format"])
        try:
            principal = self.resolve_as_user(options["as_user"])
            # A lookup answering ``None`` is refused: ``filter(...).first()`` answers it for a typo.
            if principal is None or not getattr(principal, "is_authenticated", False):
                raise PrincipalUnavailable(
                    f"The user {options['as_user']!r} resolved to nobody who can sign in."
                )
            result = dispatch(
                entry.spec,
                principal=principal,
                arguments=coerce_flat(parameters, raw),
                pool_seeds=self.pool_seeds,
                call_context=call_context,
            )
        except (DispatchError, ServiceError) as error:
            raise CommandError(_message(error), returncode=int(exit_code_for(error))) from error
        if result.kind == "not_found":
            raise CommandError(gettext("Not found."), returncode=int(ExitCode.NOT_FOUND))
        render_result(present(entry.spec, result), spec.output(), stdout, table=table)

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


def _call_context() -> dict[str, Any]:
    """A new context for the command's own reads and one run, stamped ``cli``."""
    return build_call_context(CLI_TRANSPORT)


def _sendable(
    spec: ServiceSpec | SelectorSpec, pool_seeds: PoolSeeds, call_context: dict[str, Any]
) -> Parameters:
    """What a caller may send, as the kernel's caller schema reads it: required only where dispatch demands it."""
    schema = spec_caller_input_schema(spec, pool_seeds=pool_seeds, call_context=call_context)
    required = frozenset(schema.get("required", ()))
    return Parameters.of(
        *(
            param if param.name in required else replace(param, required=False)
            for param in spec.parameters(call_context=call_context)
            if param.name in schema["properties"]
        )
    )


def _add_refused_subparser(subparsers: Any, name: str, summary: str, message: str) -> None:
    """The subcommand of a spec whose declaration refuses under the stamped dict: its reason, and no option."""
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


def _summary(spec: ServiceSpec | SelectorSpec, name: str) -> str:
    """The first paragraph of what the spec's callable says about itself, and whether it reads or writes."""
    call = spec.selector if isinstance(spec, SelectorSpec) else spec.service
    kind = "read" if isinstance(spec, SelectorSpec) else "write"
    doc = call.__doc__ if inspect.isfunction(call) or inspect.ismethod(call) else None
    first = " ".join(inspect.cleandoc(doc).split("\n\n")[0].split()) if doc else name
    return f"{first} ({kind})"


def _unsendable(parameters: Parameters) -> str | None:
    """The epilog naming the parameters no option can send, or ``None`` when there are none."""
    names = [d.name for d in describe_parameters(parameters) if not d.argv]
    return f"Takes arguments a command line cannot send: {', '.join(names)}." if names else None


def _message(error: DispatchError | ServiceError) -> str:
    """A refusal as the text a person reads: its message, and each refused field on a line."""
    if isinstance(error, InvalidArguments):
        return _with_fields(error.message, error.detail)
    if isinstance(error, ServiceValidationError) and isinstance(error.detail, Mapping | list):
        return _with_fields(error.message, error.detail)
    if isinstance(error, ActionUnavailable):
        return f"{error.message} (code: {error.code})"
    if isinstance(error, AdditionalInputRequired) and error.schema:
        options = ", ".join(option_string(key) for key in error.schema)
        return f"{error.message} Run it again with: {options}"
    return str(error.message)


def _with_fields(header: Any, detail: Any) -> str:
    """``header``, then each message in ``detail`` on its own line, after its path."""
    rows = [
        f"{'.'.join(path)}: {text}" if path else text for path, text in refusal_messages(detail)
    ]
    return "\n".join([str(header), *rows])
