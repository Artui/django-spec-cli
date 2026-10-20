"""No source in this repository reaches the kernel's copy of this package by name.

Kernel 0.10.x still ships the command half this package was moved out of, and
its root re-exports every moving name, so ``django_service_specs.ExitCode``
resolves, to the kernel's class, and a test reading it passes while testing the
wrong code. ``tests/conftest.py``'s session-finish guard sees only module
globals the run loaded; a function-local import, an attribute read through the
kernel's root and a python block in a page are invisible to it. This reads the
source instead, with ``ast``, so an import at any depth, an aliased module and
an attribute chain are all one shape.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import django_service_specs
import pytest

import django_spec_cli

REPO_ROOT = Path(__file__).resolve().parents[1]

KERNEL = "django_service_specs"
_MOVED_MODULES = ("commands", "checks", "apps")
_MOVED_PATHS = tuple(f"{KERNEL}.{module}" for module in (*_MOVED_MODULES, "types.exit_code"))
# ``__version__`` is in both roots and is each package's own, not a moved name.
FORBIDDEN = (set(django_spec_cli.__all__) & set(django_service_specs.__all__)) - {"__version__"} | {
    "check_unguarded_specs",
    "command_output",
    *_MOVED_MODULES,
}
"""Names that, read through the kernel, are the kernel's copy of this package."""

EXEMPT = {
    # The guard names the kernel's copy to look for it.
    "tests/conftest.py",
    # The guard's own tests hand it the kernel's objects to find.
    "tests/test_conftest.py",
    # This file, whose fixtures below are the shapes it rejects.
    "tests/test_kernel_copy_references.py",
}
"""Files that name the kernel's copy on purpose, each for the reason beside it."""


def _forbidden_path(path: str) -> bool:
    if path in _MOVED_PATHS or path.startswith(tuple(f"{p}." for p in _MOVED_PATHS)):
        return True
    head, _, rest = path.partition(".")
    return head == KERNEL and rest.split(".")[0] in FORBIDDEN


def _dotted(node: ast.expr) -> list[str] | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    return [node.id, *reversed(parts)]


def kernel_copy_references(source: str) -> list[str]:
    """Every reference in ``source`` that reaches the kernel's copy of this package."""
    tree = ast.parse(source)
    # Every name the kernel's root is bound to, ``import django_service_specs``
    # and ``import django_service_specs.x`` included, wherever it is bound.
    aliases = {
        alias.asname or alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == KERNEL or (alias.name.startswith(f"{KERNEL}.") and not alias.asname)
    }
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [
                f"{node.lineno}: import {alias.name}"
                for alias in node.names
                if _forbidden_path(alias.name)
            ]
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == KERNEL:
            module = node.module or ""
            found += [
                f"{node.lineno}: from {module} import {alias.name}"
                for alias in node.names
                if _forbidden_path(module) or alias.name in FORBIDDEN
            ]
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            parts = _dotted(node)
            if parts and parts[0] in aliases:
                path = [KERNEL, *parts[1:]]
                # The shortest forbidden prefix of a chain only, so one read
                # is one finding: ``k.SpecCommand.help`` reports
                # ``k.SpecCommand``.
                if _forbidden_path(".".join(path)) and not _forbidden_path(".".join(path[:-1])):
                    found.append(f"{node.lineno}: {'.'.join(parts)}")
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            # A dotted path handed to ``monkeypatch.setattr`` or ``import_module``.
            and re.fullmatch(rf"{KERNEL}(\.\w+)+", node.value)
            and _forbidden_path(node.value)
        ):
            found.append(f"{node.lineno}: {node.value!r}")
    return found


def _python_sources() -> list[Path]:
    return sorted(
        path
        for directory in ("django_spec_cli", "tests", "docs")
        for path in (REPO_ROOT / directory).rglob("*.py")
        if path.relative_to(REPO_ROOT).as_posix() not in EXEMPT
    )


def _page_blocks() -> list[tuple[str, int, str]]:
    blocks = []
    for page in sorted([*(REPO_ROOT / "docs").glob("*.md"), REPO_ROOT / "README.md"]):
        for index, block in enumerate(re.findall(r"```python\n(.*?)```", page.read_text(), re.S)):
            # A snippet include names a file under docs/examples, read above.
            if "--8<--" not in block:
                blocks.append((page.relative_to(REPO_ROOT).as_posix(), index, block))
    return blocks


def test_the_sources_read_are_the_package_the_suite_and_the_pages() -> None:
    # An empty walk would pass the two tests below with nothing read.
    read = {path.relative_to(REPO_ROOT).as_posix() for path in _python_sources()}
    assert {"django_spec_cli/spec_command.py", "docs/examples/commands.py"} <= read
    assert {"tests/test_checks.py", "tests/test_spec_command.py"} <= read
    assert {page for page, _, _ in _page_blocks()} == {"README.md", "docs/index.md"}
    assert {"SpecCommand", "ExitCode", "exit_code_for"} <= FORBIDDEN


@pytest.mark.parametrize(
    "path", _python_sources(), ids=lambda path: path.relative_to(REPO_ROOT).as_posix()
)
def test_no_module_reaches_the_kernel_s_copy(path: Path) -> None:
    assert kernel_copy_references(path.read_text()) == []


@pytest.mark.parametrize(
    ("page", "index", "block"), _page_blocks(), ids=lambda value: str(value)[:20]
)
def test_no_python_block_on_a_page_reaches_the_kernel_s_copy(
    page: str, index: int, block: str
) -> None:
    assert kernel_copy_references(block) == [], (page, index)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "import django_service_specs\ndjango_service_specs.ExitCode\n",
            ["2: django_service_specs.ExitCode"],
        ),
        ("import django_service_specs as k\nk.SpecCommand.help\n", ["2: k.SpecCommand"]),
        (
            "import django_service_specs.registry\ndjango_service_specs.exit_code_for(e)\n",
            ["2: django_service_specs.exit_code_for"],
        ),
        (
            "def f():\n    from django_service_specs import ExitCode\n",
            ["2: from django_service_specs import ExitCode"],
        ),
        (
            "from django_service_specs.settings import command_output\n",
            ["1: from django_service_specs.settings import command_output"],
        ),
        (
            "from django_service_specs import check_unguarded_specs\n",
            ["1: from django_service_specs import check_unguarded_specs"],
        ),
        (
            "from django_service_specs.commands.argv import utils\n",
            ["1: from django_service_specs.commands.argv import utils"],
        ),
        (
            "import django_service_specs.types.exit_code\n",
            ["1: import django_service_specs.types.exit_code"],
        ),
        (
            "import django_service_specs\ndjango_service_specs.types.exit_code.ExitCode\n",
            ["2: django_service_specs.types.exit_code"],
        ),
        (
            "patch('django_service_specs.checks.get_commands')\n",
            ["1: 'django_service_specs.checks.get_commands'"],
        ),
    ],
)
def test_each_route_to_the_kernel_s_copy_is_found(source: str, expected: list[str]) -> None:
    assert kernel_copy_references(source) == expected


@pytest.mark.parametrize(
    "source",
    [
        "from django_service_specs import SpecRegistry, unguarded_specs\n",
        "import django_service_specs\ndjango_service_specs.REFUSALS\n",
        "from django_service_specs.adapters.pydantic import PydanticPresenter\n",
        "from django_spec_cli import ExitCode, SpecCommand\n",
        "ids = ['django_service_specs.W001', 'django_service_specs']\n",
        "import other as django_service_specs\nother.ExitCode\n",
    ],
)
def test_a_kernel_name_that_stays_the_kernel_s_is_not_found(source: str) -> None:
    assert kernel_copy_references(source) == []
