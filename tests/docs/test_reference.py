"""The API reference documents every name the package root exports, at its own path."""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import django_spec_cli

PAGE = Path(__file__).resolve().parents[2] / "docs" / "reference.md"


def _documented() -> dict[str, object]:
    found: dict[str, object] = {}
    for path in re.findall(r"^::: (\S+)$", PAGE.read_text(), re.M):
        module, _, name = path.rpartition(".")
        found[name] = getattr(importlib.import_module(module), name)
    return found


def test_every_root_name_has_an_entry_for_the_root_s_own_object() -> None:
    documented = _documented()
    exported = {name for name in django_spec_cli.__all__ if name != "__version__"}
    assert set(documented) == exported
    for name in exported:
        assert documented[name] is getattr(django_spec_cli, name), name


def test_the_setting_and_both_check_ids_are_documented() -> None:
    page = PAGE.read_text()
    for spelling in ("SPEC_CLI_OUTPUT", "django_spec_cli.W001", "django_spec_cli.W003"):
        assert f"`{spelling}`" in page, spelling
