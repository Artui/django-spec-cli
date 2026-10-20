"""Suite-wide hooks: the guard that the suite tests this package and not the kernel's copy.

Kernel 0.10.x still ships the command half this package was moved out of:
``django_service_specs.commands``, ``types/exit_code.py``, ``checks.py`` and
``apps.py``, and its root re-exports every moving name. A missed import rewrite
therefore still resolves, against the kernel's copy, and a test passes while
testing the wrong code. Nothing at import fails, so the guard reads what the run
actually loaded once it is over.

It cannot ask that ``django_service_specs.commands`` stay out of ``sys.modules``:
the kernel's root imports it, and every kernel name this package reads comes
through the root. It asks the two questions that do separate the copies:

- the kernel's ``checks`` and ``apps`` are never imported, which nothing does
  while the test settings list no kernel app, except a ``monkeypatch`` string
  or an import still naming them;
- no module of this package, of the suite or of the docs examples holds an
  object the kernel's copy defines: a module, class or function from one of the
  moving kernel modules, or the kernel's ``command_output``, which lives in a
  module that does not move.
"""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

import pytest

_KERNEL_COPY = (
    "django_service_specs.commands",
    "django_service_specs.types.exit_code",
    "django_service_specs.checks",
    "django_service_specs.apps",
)
_NEVER_IMPORTED = ("django_service_specs.checks", "django_service_specs.apps")
_OURS = ("django_spec_cli", "tests", "docs")


def _within(name: str, packages: tuple[str, ...]) -> bool:
    return any(name == package or name.startswith(f"{package}.") for package in packages)


def _kernel_copy_of(value: Any) -> str | None:
    """The kernel module ``value`` comes from, when that module is the kernel's copy.

    The ``command_output`` name condition is held by
    test_the_guard_passes_the_kernel_s_settings_reader_that_stays_the_kernel_s,
    the module condition beside it by
    test_the_guard_passes_this_package_s_own_setting_reader.
    """
    if isinstance(value, ModuleType):
        origin = value.__name__
    else:
        origin = getattr(value, "__module__", None)
        if not isinstance(origin, str):
            return None
        if origin == "django_service_specs.settings" and (
            getattr(value, "__name__", None) == "command_output"
        ):
            return f"{origin}.command_output"
    return origin if _within(origin, _KERNEL_COPY) else None


def kernel_copies_loaded(modules: dict[str, ModuleType | None]) -> list[str]:
    """Every place in ``modules`` that reaches the kernel's copy of this package.

    The ``module is None`` condition is held by
    test_the_guard_skips_a_module_import_blocked_with_none, the package
    condition beside it by test_the_guard_reads_only_this_repository_s_modules.
    """
    found = [f"{name} is imported" for name in _NEVER_IMPORTED if name in modules]
    for name, module in sorted(modules.items()):
        if not _within(name, _OURS) or module is None:
            continue
        for attribute, value in sorted(vars(module).items(), key=lambda item: item[0]):
            origin = _kernel_copy_of(value)
            if origin is not None:
                found.append(f"{name}.{attribute} is the kernel's {origin}")
    return found


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    found = kernel_copies_loaded(dict(sys.modules))
    if found:
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        lines = ["The suite reached the kernel's copy of this package:", *found]
        if reporter is not None:
            reporter.write_line("\n".join(lines), red=True)
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
