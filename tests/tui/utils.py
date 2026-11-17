from __future__ import annotations

from typing import Any

from django_service_specs import DEFAULT_POOL_SEEDS, RegisteredSpec, SpecRegistry

from django_spec_cli.tui.spec_tui import SpecTui


def entries_of(registry: SpecRegistry) -> dict[str, RegisteredSpec]:
    """``registry`` keyed by subcommand, as ``SpecCommand`` hands it over."""
    return {entry.name.replace("_", "-"): entry for entry in registry}


def app_over(
    registry: SpecRegistry, principal: Any = None, refusals: dict[str, str] | None = None
) -> SpecTui:
    return SpecTui(
        entries=entries_of(registry),
        refusals=refusals or {},
        principal=principal,
        pool_seeds=DEFAULT_POOL_SEEDS,
        command_label="notes",
    )
