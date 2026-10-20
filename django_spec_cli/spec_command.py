"""``SpecCommand`` - a registry of specs as one management command."""

from __future__ import annotations

import argparse
import inspect
from collections.abc import Mapping
from typing import Any, TextIO, cast

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils.translation import gettext

from django_service_specs.authorization.principal_unavailable import PrincipalUnavailable
from django_service_specs.authorization.resolve_principal import resolve_principal
from django_service_specs.commands.argv.add_spec_arguments import add_spec_arguments
from django_service_specs.commands.argv.describe_parameters import describe_parameters
from django_service_specs.commands.argv.parsed_arguments import parsed_arguments
from django_service_specs.commands.argv.utils import option_string
from django_service_specs.commands.exit_code_for import exit_code_for
from django_service_specs.commands.render.render_result import render_result
from django_service_specs.commands.render.wants_table import wants_table
from django_service_specs.commands.report.unguarded_message import unguarded_message
from django_service_specs.dispatch.dispatch import dispatch
from django_service_specs.dispatch.present import present
from django_service_specs.dispatch.relax_partial import relax_partial
from django_service_specs.parameters.coerce_flat import coerce_flat
from django_service_specs.parameters.invalid_arguments import InvalidArguments
from django_service_specs.parameters.parameters import Parameters
from django_service_specs.parameters.refusal_messages import refusal_messages
from django_service_specs.pool.pool_seeds import DEFAULT_POOL_SEEDS, PoolSeeds
from django_service_specs.registry.registered_spec import RegisteredSpec
from django_service_specs.registry.spec_registry import SpecRegistry
from django_service_specs.registry.unguarded_specs import unguarded_specs
from django_service_specs.services.action_unavailable import ActionUnavailable
from django_service_specs.services.additional_input_required import AdditionalInputRequired
from django_service_specs.services.service_error import ServiceError
from django_service_specs.services.service_validation_error import ServiceValidationError
from django_service_specs.specs.kernel_spec import kernel_spec
from django_service_specs.specs.selector_spec import SelectorSpec
from django_service_specs.specs.server_owned_keys import server_owned_keys
from django_service_specs.specs.service_spec import ServiceSpec
from django_service_specs.types.dispatch_error import DispatchError
from django_service_specs.types.exit_code import ExitCode

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
    ``SpecView.pool_seeds`` does, for a registry whose callables read one.

    It is run as ``manage.py <command> <spec> --as-user USER [--json|--table]
    [--option value ...]``, or ``manage.py <command> --explain``:

    - **One subcommand per registry entry**, named after the entry with each
      ``_`` shown as ``-``. Its options are the spec's parameters, as
      [`add_spec_arguments`][django_service_specs.commands.argv.add_spec_arguments.add_spec_arguments]
      spells them, less any key the server fills
      ([`server_owned_keys`][django_service_specs.specs.server_owned_keys.server_owned_keys]).
      No option is matched by a prefix: an abbreviation is refused rather
      than read as whichever option it begins.
    - **``--as-user`` is required.** Its value goes through
      [`resolve_as_user`][django_service_specs.commands.spec_command.SpecCommand.resolve_as_user],
      and the user it returns is the principal ``dispatch`` runs the spec
      for, with the permission checks enforced: the command passes no
      ``Grant``, and opens no transaction of its own.
    - The result goes through the spec's presenter and is written as a table
      or as JSON Lines: ``--table`` and ``--json`` choose, then the
      ``SERVICE_SPECS_COMMAND_OUTPUT`` setting, then whether stdout is a
      terminal ([`wants_table`][django_service_specs.commands.render.wants_table.wants_table]).
    - A refusal ends the run with a ``CommandError`` carrying its message and
      an [`ExitCode`][django_service_specs.types.exit_code.ExitCode].
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

    def create_parser(self, prog_name: str, subcommand: str, **kwargs: Any) -> CommandParser:
        """Django's parser, with this command's options added and no option read by its prefix."""
        self._command_label = subcommand
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
            parameters = _sendable(spec)
            summary = _summary(spec, entry.name)
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
        spec = kernel_spec(entry.spec)
        parameters = spec.parameters()
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


def _sendable(spec: ServiceSpec | SelectorSpec) -> Parameters:
    """What a caller may send, as the shape check reads it: required only where dispatch demands it.

    Relaxed for ``partial`` by the shape check's own reading, so ``--help``
    marks ``(required)`` exactly where an omission is refused
    (test_a_partial_spec_requires_only_what_names_its_row), and without the
    keys the server fills, whose value a caller's would never replace
    (test_a_key_the_server_fills_is_no_option).
    """
    owned = server_owned_keys(spec)
    relaxed = relax_partial(spec, spec.parameters())
    return Parameters.of(*(param for param in relaxed if param.name not in owned))


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
