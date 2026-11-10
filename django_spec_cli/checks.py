from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from django.apps import AppConfig
from django.core.checks import CheckMessage, Warning
from django.core.exceptions import ImproperlyConfigured
from django.core.management import get_commands, load_command_class
from django_service_specs import UnguardedSpec, check_seeds, unguarded_specs

from django_spec_cli.report.unguarded_message import unguarded_message
from django_spec_cli.report.utils import refused_message
from django_spec_cli.spec_command import SpecCommand

_HINT = (
    "Declare a PermissionCheck that refuses someone in the spec's permissions, or add "
    "'django_spec_cli.W001' to SILENCED_SYSTEM_CHECKS if the spec is meant to be open."
)
_REFUSED_HINT = (
    "Change the declaration as the message says. Until then a run of the spec is refused, "
    "whether or not django_spec_cli.W004 is silenced."
)


def check_unguarded_specs(
    app_configs: Sequence[AppConfig] | None, **kwargs: Any
) -> list[CheckMessage]:
    """Warn once per spec that authorizes nothing or can't run, in every project ``SpecCommand``."""
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
                    id="django_spec_cli.W003",
                )
            )
            continue
        command, specs = loaded
        messages.extend(
            Warning(
                unguarded_message(spec, name),
                hint=_HINT,
                obj=type(command),
                id="django_spec_cli.W001",
            )
            for spec in specs
        )
        messages.extend(
            Warning(
                refused_message(spec_name, name, error),
                hint=_REFUSED_HINT,
                obj=type(command),
                id="django_spec_cli.W004",
            )
            for spec_name, error in _refused(command)
        )
    return messages


def _refused(command: SpecCommand) -> Iterator[tuple[str, ImproperlyConfigured]]:
    """Each spec of ``command`` a run refuses as declared, with its refusal, in registry order."""
    for entry in command.registry:
        try:
            check_seeds(entry.spec, pool_seeds=command.pool_seeds)
        except ImproperlyConfigured as error:
            yield entry.name, error
            continue
        declared = command._refused_by_declaration.get(entry.name)
        if declared is not None:
            yield entry.name, declared


def _spec_commands(
    app_configs: Sequence[AppConfig] | None,
) -> Iterator[tuple[str, str, tuple[SpecCommand, tuple[UnguardedSpec, ...]] | Exception]]:
    """Each ``SpecCommand`` the project serves: its unguarded specs, or why it will not load."""
    wanted = None if app_configs is None else {config.name for config in app_configs}
    for name, app_name in get_commands().items():
        if app_name == "django.core" or (wanted is not None and app_name not in wanted):
            continue
        try:
            command = load_command_class(app_name, name)
            if not isinstance(command, SpecCommand):
                continue
            command.create_parser("manage.py", name)
            loaded: tuple[SpecCommand, tuple[UnguardedSpec, ...]] | Exception = (
                command,
                unguarded_specs(command.registry),
            )
        except Exception as error:
            loaded = error
        yield name, app_name, loaded
