from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType

import django_spec_cli


def _subpackages() -> list[ModuleType]:
    return [
        importlib.import_module(info.name)
        for info in pkgutil.walk_packages(
            django_spec_cli.__path__, prefix=f"{django_spec_cli.__name__}."
        )
        if info.ispkg
    ]


def test_the_package_has_the_subpackages_it_re_exports() -> None:
    # The two tests below walk the subpackages, so an empty walk would pass them both.
    assert sorted(package.__name__ for package in _subpackages()) == [
        "django_spec_cli.argv",
        "django_spec_cli.render",
        "django_spec_cli.report",
        "django_spec_cli.types",
    ]


def test_every_subpackage_name_is_re_exported_at_the_root() -> None:
    # A name in a subpackage's __all__ but not the root is public in one place only.
    missing = {
        f"{package.__name__}.{name}"
        for package in _subpackages()
        for name in package.__all__
        if name not in django_spec_cli.__all__
    }
    assert not missing


def test_each_root_name_is_the_subpackage_s_own_object() -> None:
    # Identity, not equality: each root name is the subpackage's own object.
    for package in _subpackages():
        for name in package.__all__:
            assert getattr(django_spec_cli, name) is getattr(package, name), name


def test_the_root_names_nothing_it_does_not_define() -> None:
    assert [name for name in django_spec_cli.__all__ if not hasattr(django_spec_cli, name)] == []


def test_the_root_serves_the_command_its_outcome_map_and_the_version() -> None:
    # The three root names no subpackage exports, so the walk above cannot see one go missing.
    assert {"SpecCommand", "exit_code_for", "__version__"} <= set(django_spec_cli.__all__)
