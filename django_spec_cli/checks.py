"""The system check reporting every spec a ``SpecCommand`` serves that authorizes nothing."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from django.apps import AppConfig
from django.core.checks import CheckMessage, Warning
from django.core.management import get_commands, load_command_class

from django_service_specs.commands.report.unguarded_message import unguarded_message
from django_service_specs.commands.report.unguarded_spec import UnguardedSpec
from django_service_specs.commands.report.unguarded_specs import unguarded_specs
from django_service_specs.commands.spec_command import SpecCommand

_HINT = (
    "Declare a PermissionCheck that refuses someone in the spec's permissions, or add "
    "'django_service_specs.W001' to SILENCED_SYSTEM_CHECKS if the spec is meant to be open."
)


def check_unguarded_specs(
    app_configs: Sequence[AppConfig] | None, **kwargs: Any
) -> list[CheckMessage]:
    """Warn once per spec that authorizes nothing, in every ``SpecCommand`` of the project.

    Registered by the app's ``ready()``, so a project gets it by listing
    ``django_service_specs`` in ``INSTALLED_APPS`` and not otherwise. There is
    no global registry to read: each ``SpecCommand`` subclass names its own,
    so the check finds them the way ``manage.py`` does, by loading every
    command the installed apps serve and keeping the ``SpecCommand`` ones.
    Loading a command imports its module and constructs it, third-party
    commands included; Django's own are not loaded, since none is a
    ``SpecCommand``.

    - ``django_service_specs.W001``, one per spec that
      [`unguarded_specs`][django_service_specs.commands.report.unguarded_specs.unguarded_specs]
      reports, naming the command an operator types and the spec, with the
      command class as ``obj``. A ``Warning``, never an ``Error``: an open
      spec is a decision or an accident the check cannot tell apart, and an
      ``Error`` would stop ``migrate`` on a project working as intended.
      ``SILENCED_SYSTEM_CHECKS`` silences it by id, so for every spec at once.
    - ``django_service_specs.W003``, one per command that could not be loaded or
      whose parser could not be built, naming it and the error. Without this app nothing loads that command
      until somebody runs it, so failing the check on it would make a broken
      command nobody runs stop ``migrate``; and dropping it silently would
      leave its specs unchecked with nothing saying so.

    With ``app_configs``, as ``manage.py check <app_label>`` passes, only
    those apps' commands are loaded.

    The check runs wherever system checks run: ``manage.py check``, and
    every ``manage.py`` command that keeps ``requires_system_checks``.
    ``call_command`` skips system checks for every command but ``check``
    itself, so a command invoked through it does not run this.
    """
    messages: list[CheckMessage] = []
    for name, app_name, loaded in _spec_commands(app_configs):
        if isinstance(loaded, Exception):
            messages.append(
                Warning(
                    f"The command {name!r} from {app_name} could not be set up, so its specs "
                    f"were not checked: {type(loaded).__name__}: {loaded}",
                    hint=(
                        f"Run manage.py {name} to see the traceback. Until it loads, the specs "
                        "it serves are not checked."
                    ),
                    id="django_service_specs.W003",
                )
            )
            continue
        command, specs = loaded
        messages.extend(
            Warning(
                unguarded_message(spec, name),
                hint=_HINT,
                obj=type(command),
                id="django_service_specs.W001",
            )
            for spec in specs
        )
    return messages


def _spec_commands(
    app_configs: Sequence[AppConfig] | None,
) -> Iterator[tuple[str, str, tuple[SpecCommand, tuple[UnguardedSpec, ...]] | Exception]]:
    """Each ``SpecCommand`` the project serves with its unguarded specs, or why it would not load.

    The one place that reads Django's management internals: ``get_commands``
    maps each command name to the app serving it, and
    ``load_command_class`` imports that module and constructs its
    ``Command``. Neither is documented API, so
    ``tests/test_checks.py``'s ``TestTheDjangoInternalsTheWalkReads`` pins the
    shape this relies on.

    Reading the registry is inside the same ``try``, so a ``SpecCommand``
    that names none is reported like one that would not construct.
    """
    wanted = None if app_configs is None else {config.name for config in app_configs}
    for name, app_name in get_commands().items():
        # One arc to coverage, so each operand is named by the test that fails
        # without it: ``django.core`` by test_django_s_own_commands_are_not_loaded,
        # the ``wanted`` clause by test_an_app_not_named_has_its_commands_skipped,
        # and its ``not in`` by test_the_app_named_has_its_commands_checked.
        # Django's own commands are skipped by app rather than by name, since a
        # project command overriding one maps to the project's app
        # (test_a_project_command_under_a_core_name_is_walked); loading them
        # all costs more than the rest of the walk.
        if app_name == "django.core" or (wanted is not None and app_name not in wanted):
            continue
        try:
            command = load_command_class(app_name, name)
            if not isinstance(command, SpecCommand):
                continue
            # Built as ``manage.py`` builds it, so a command whose parser
            # cannot be built (a parameter taking an option the command owns,
            # two specs sharing a subcommand name) is reported here and not
            # first found by the operator running it.
            command.create_parser("manage.py", name)
            loaded: tuple[SpecCommand, tuple[UnguardedSpec, ...]] | Exception = (
                command,
                unguarded_specs(command.registry),
            )
        # Anything a module, a constructor or the parser's construction raises: an ``ImportError`` from a
        # missing dependency, an ``ImproperlyConfigured`` from a registry
        # refusing a spec at import, or the command's own bug. Not
        # ``BaseException``, so an interrupt still stops the check.
        except Exception as error:
            loaded = error
        yield name, app_name, loaded
