"""``SpecCommand`` - a registry of specs as one management command."""

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
      under ``pool_seeds`` and the stamped ``call_context``): less any key the server fills, and required only
      where dispatch refuses leaving it out.
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
    help = "Run one operation of a registry of specs, as the user --as-user names."

    _command_label: str
    _parser: CommandParser
    _entries: dict[str, RegisteredSpec]
    _refused_by_declaration: dict[str, ImproperlyConfigured]

    def create_parser(self, prog_name: str, subcommand: str, **kwargs: Any) -> CommandParser:
        """Django's parser, with this command's options added and no option read by its prefix."""
        self._command_label = subcommand
        # Before ``add_arguments``, and not in it: a subclass overriding that
        # without calling ``super()`` still leaves the system check a dict to read.
        self._refused_by_declaration = {}
        parser = super().create_parser(prog_name, subcommand, **kwargs)
        # Django's own options are on this parser, and a prefix of one is no
        # more an option here than on a subcommand.
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
        # Every option string the command owns: its subcommands' own and
        # Django's. ``manage.py`` reads ``--settings`` and ``--pythonpath``
        # from anywhere on the line, so a spec option of either name would
        # configure Django instead. Read from argparse's map of option
        # strings, which carries no public reader, so Django's list is never
        # copied here to drift.
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
                # Only the read made under the stamped dict can raise here: a
                # declaration the kernel refuses outside a call is
                # ``check_seeds``' and is asked in ``handle``. Raising from the
                # parser would stop every spec the command serves, ``--help``
                # and ``--explain`` with them, so the refusal waits for a run of
                # this spec, which raises it, and its subcommand takes no option.
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
                # Without it, ``--as-user 7`` beside a parameter ``as_user_id``
                # is one typo from ``--as-user-i 7``, which argparse would read
                # as ``--as-user-id``.
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
        # Asked of the one spec named, not of every entry where the parser is
        # built: a raise there would stop every spec the command serves, and
        # ``--help`` and ``--explain`` with them. Before the lookup, so a
        # project's ``resolve_as_user`` never runs for a spec that cannot.
        # Not a ``CommandError``: the declaration is wrong, not the call, and
        # ``ExitCode.ERROR`` is published as the failure with a traceback.
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
        # One dict for the whole run, built ahead of the first callable it
        # asks: the declaration read here, then every stage ``dispatch`` runs,
        # so a callable reading ``transport`` sees ``cli`` from either.
        call_context = _call_context()
        parameters = spec.parameters(call_context=call_context)
        raw = parsed_arguments(argparse.Namespace(**options), parameters)
        # Read before the run, not after it: a setting that names no format
        # raises, and raising once a write has committed reports a failure for
        # an operation that happened, which a script retries.
        # Django's ``OutputWrapper`` is an ``io.TextIOBase`` rather than a
        # ``typing.TextIO``, and answers the ``write`` and ``isatty`` both
        # functions read for the stream it wraps.
        stdout = cast("TextIO", self.stdout)
        table = wants_table(stdout, requested=options["output_format"])
        try:
            principal = self.resolve_as_user(options["as_user"])
            # A lookup is the project's, and ``filter(...).first()`` is the
            # obvious one: a typo then answers ``None``, which an open spec
            # would run for. Each condition is held by its own test:
            # test_a_lookup_answering_none_is_refused and
            # test_a_lookup_answering_an_anonymous_user_is_refused.
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
    """A new context for the command's own reads and one run, stamped ``cli``.

    ``request`` and ``view`` are there as ``None``, since a command line has
    neither: the kernel hands a callable declaring either ``None`` for a
    ``None`` entry exactly as for a missing one, so no binding changes.
    ``format`` and ``action`` are no pool names and are never bound.
    """
    return build_call_context(CLI_TRANSPORT)


def _sendable(
    spec: ServiceSpec | SelectorSpec, pool_seeds: PoolSeeds, call_context: dict[str, Any]
) -> Parameters:
    """What a caller may send, as the kernel's caller schema reads it: required only where dispatch demands it.

    The parameters ``spec_caller_input_schema`` offers under the command's
    ``pool_seeds`` and the stamped ``call_context``, so a field a Validator
    declares only to ``cli`` is an option and one declared to another
    transport is not
    (test_a_required_field_declared_only_under_cli_is_an_option_marked_required,
    test_a_field_declared_under_another_transport_is_no_option), and no key the
    server fills is an option: one a provider
    is annotated to fill (test_a_key_the_server_fills_is_no_option), and a
    reflected read a registered seed fills
    (test_a_reflected_read_a_seed_fills_is_an_option_only_without_the_seed).
    Each is relaxed where the schema does not require it, so ``--help``
    marks ``(required)`` exactly where an omission is refused: on a
    ``partial`` spec (test_a_partial_spec_requires_only_what_names_its_row)
    and beside a provider that may fill it
    (test_a_read_a_provider_may_fill_is_offered_and_not_required). A read
    stays declared required where the provider takes it by name with no
    default, since that provider cannot be the one to fill it
    (test_a_read_a_provider_requires_itself_is_required). Only
    relaxed, never made required, so a declared default still answers.
    """
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
    """The subcommand of a spec whose declaration refuses under the stamped dict: its reason, and no option.

    Whatever is sent after the name is taken and read by nothing, so a run is
    refused with the reason whatever it carried, as a spec ``check_seeds``
    refuses is. Only ``--help`` is read, and it prints the reason.
    """
    subparser = subparsers.add_parser(
        name,
        help=summary.replace("%", "%%"),
        description=summary,
        # argparse formats an epilog only where it names ``%(prog)``, so a
        # ``%`` is doubled there and nowhere else
        # (test_a_percent_sign_in_the_reason_is_printed_as_it_is).
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
    """The first paragraph of what the spec's callable says about itself, and whether it reads or writes.

    Only a function's or a method's own docstring: a ``partial`` or a
    callable object answers with its class's, which describes the class and
    not the operation. With none, the registered name stands in. Both halves
    of the guard are held by test_only_a_function_s_or_a_method_s_own_docstring_is_read:
    its bound method (``ismethod``) and its ``partial`` (the guard itself).
    """
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
    # Two conditions, each held by a case of test_a_service_s_refusal_is_its_exit_code:
    # [other] for the type (a plain ServiceError has no ``detail``) and
    # [validation] for the detail (a string is one message, not a tree).
    if isinstance(error, ServiceValidationError) and isinstance(error.detail, Mapping | list):
        return _with_fields(error.message, error.detail)
    if isinstance(error, ActionUnavailable):
        return f"{error.message} (code: {error.code})"
    # Two conditions, each held by a case of test_a_service_s_refusal_is_its_exit_code:
    # [other] for the type (a plain ServiceError has no ``schema``) and
    # [input_bare] for the schema (with none there is nothing to name).
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
