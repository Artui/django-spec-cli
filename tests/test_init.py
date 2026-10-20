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
    # The two tests below walk the subpackages, so an empty walk would pass
    # them both with nothing checked.
    assert sorted(package.__name__ for package in _subpackages()) == [
        "django_spec_cli.argv",
        "django_spec_cli.render",
        "django_spec_cli.report",
        "django_spec_cli.types",
    ]


def test_every_subpackage_name_is_re_exported_at_the_root() -> None:
    # A subpackage's ``__all__`` is its public surface, and the root is where a
    # consumer reads the whole of it. A name added to a subpackage and not to
    # the root is public in one place and missing from the other, and nothing
    # else in the suite notices, because every test imports from leaf paths.
    missing = {
        f"{package.__name__}.{name}"
        for package in _subpackages()
        for name in package.__all__
        if name not in django_spec_cli.__all__
    }
    assert not missing


def test_each_root_name_is_the_subpackage_s_own_object() -> None:
    # Identity rather than equality: a second definition of one name would
    # pass ``==`` for a class compared with itself nowhere, and an
    # ``isinstance`` against the other copy would fail in a consumer.
    for package in _subpackages():
        for name in package.__all__:
            assert getattr(django_spec_cli, name) is getattr(package, name), name


def test_the_root_names_nothing_it_does_not_define() -> None:
    assert [name for name in django_spec_cli.__all__ if not hasattr(django_spec_cli, name)] == []


def test_the_root_serves_the_command_its_outcome_map_and_the_version() -> None:
    # The three root names no subpackage exports, so the walk above cannot
    # see one go missing.
    assert {"SpecCommand", "exit_code_for", "__version__"} <= set(django_spec_cli.__all__)
