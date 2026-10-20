from __future__ import annotations

import sys
from types import ModuleType

import django_service_specs

from tests.conftest import kernel_copies_loaded


def _module(name: str, **values: object) -> ModuleType:
    module = ModuleType(name)
    vars(module).update(values)
    return module


def test_the_guard_finds_a_name_imported_from_the_kernel_s_copy() -> None:
    # Read off the root inside the test, never held as a global here, or the
    # guard would find this module too.
    copy = django_service_specs.SpecCommand
    found = kernel_copies_loaded({"tests.stray": _module("tests.stray", SpecCommand=copy)})
    assert found == [
        "tests.stray.SpecCommand is the kernel's django_service_specs.commands.spec_command"
    ]


def test_the_guard_finds_a_kernel_copy_module_and_the_kernel_s_setting_reader() -> None:
    commands = sys.modules["django_service_specs.commands"]
    reader = sys.modules["django_service_specs.settings"].command_output
    found = kernel_copies_loaded(
        {"docs.stray": _module("docs.stray", commands=commands, command_output=reader)}
    )
    assert found == [
        "docs.stray.command_output is the kernel's django_service_specs.settings.command_output",
        "docs.stray.commands is the kernel's django_service_specs.commands",
    ]


def test_the_guard_finds_the_kernel_s_checks_imported_at_all() -> None:
    found = kernel_copies_loaded({"django_service_specs.checks": _module("x")})
    assert found == ["django_service_specs.checks is imported"]


def test_the_guard_reads_only_this_repository_s_modules() -> None:
    copy = django_service_specs.SpecCommand
    assert kernel_copies_loaded({"elsewhere": _module("elsewhere", SpecCommand=copy)}) == []
