# django-spec-cli

Guidance for working in this repository.

## What this package is

The management-command transport for `django-service-specs`. A project
subclasses `SpecCommand`, names a `SpecRegistry`, and `manage.py <command>`
serves one subcommand per spec: an option for each parameter, a principal named
by `--as-user`, the result as a table or JSON Lines, and an exit code for every
refusal. Two system checks, `django_spec_cli.W001` and `W003`, report a served
spec that authorizes nothing and a command that cannot be loaded.

It is the kernel's `commands/` subpackage, moved out with its history so that
the kernel can carry no transport, and the kernel carries no copy of it from
0.11.0. Two positions follow from the move:

- **The kernel is read through its root and nothing else.** Every kernel name
  this package uses is in `django_service_specs.__all__`, and every import of
  one goes through `from django_service_specs import ...`. A separate
  distribution that reaches a kernel module path breaks on the kernel's next
  internal move, and nothing here would fail first.
- **The kernel's behaviour is not restated here.** Dispatch, authorization,
  argument coercion and the refusal types are the kernel's; this package maps
  them onto argv, stdout and an exit status. The outcome map, `exit_code_for`,
  is held against the kernel's own list of refusals with the kernel's
  `unanswered_refusals`, so a refusal the kernel adds fails a test here.

## Commands

| Command | Does |
| --- | --- |
| `make init` | Sync all dependency groups and install the pre-commit hooks |
| `make test` | pytest with the 100% line+branch coverage gate |
| `make lint` | `ruff check` plus `ty check` |
| `make format-check` | `ruff format --check --diff` (CI runs this; `make lint` does not) |
| `make docs-build` | `mkdocs build --strict` |
| `make release-bump VERSION=X.Y.Z` | Rewrite the version and promote the changelog section |

## Structural rules

Non-negotiable. They keep the package navigable, and they are the kernel's.

1. **One exported class or function per file.** The file is named after the
   exported symbol in `snake_case`.
2. **Private helpers used only in one file** stay in that file with a `_name`
   prefix.
3. **Non-exported helpers shared across files** go in that package's `utils.py`.
4. **Top-level imports only.** Lazy or function-local imports are forbidden
   unless the import targets a declared optional dependency gated behind an
   opt-in. Document the reason inline. A circular import is never the reason
   (rule 9).
5. **Full type annotations on every function and method signature.** `Any` is
   allowed only at the Django boundary where the type genuinely is `Any`.
6. **`__init__.py` is the only re-export point.** Each `__init__.py` lists the
   public surface in `__all__`. Internal modules import from leaf paths, never
   from the package's `__init__`.
7. **The package root is a table of contents, not a drawer.** It holds
   `__init__.py`, `version.py`, `settings.py`, `apps.py`, `checks.py`, and the
   two modules the whole package exists for: `spec_command.py`, the command
   class, and `exit_code_for.py`, its outcome map. Everything else lives in a
   subpackage named for a **concern**: `argv/` (parameters as options and back),
   `render/` (a result on stdout) and `report/` (what the system check says).
   `types/` is the one standing subpackage, for value types.
8. **`types/` imports nothing else in the package.** A subpackage's `__init__`
   re-exports its whole surface, so a module every subpackage imports must sit
   in a package whose `__init__` pulls in nothing.
9. **No `if TYPE_CHECKING:` guard.** A guard hides an import cycle from the
   interpreter while the type checker still sees it. The ban is ruff's
   `TID251`, so `make lint` and CI run it. Break a cycle by structure, never by
   a function-local import (rule 4).

## Naming the concepts

**One spelling each, so a rename is a replace.** No aliases, no
backwards-compatible second name, no re-export under an old spelling.
`django-spec-cli` and `django_spec_cli` appear verbatim and nowhere derived, and
so do the check ids and the setting key, `SPEC_CLI_OUTPUT`.

## Constraints that look like tidy-ups

Each of these reads as an oversight and is not.

- **The checks are registered by this package's own `AppConfig`.** A project
  lists `"django_spec_cli"` in `INSTALLED_APPS` to get `W001` and `W003`. The
  kernel keeps the registry fact the check reads, `unguarded_specs`, because
  another transport can ask the same question of a registry. The kernel's own
  app stays importable and registers nothing, so listing only it gets no check
  (`tests/test_checks.py`, `test_the_kernel_s_app_registers_no_check_of_its_own`).
- **The test settings list no kernel app.** The package needs nothing of the
  kernel switched on, and the suite shows it.

## Tests

`tests/` mirrors the source tree, one file per source file with the same name.
`pytest-asyncio` runs in auto mode. The coverage gate is **100% line and
branch**.

Never `# pragma: no cover`. If a branch cannot be reached, that is a signal to
restructure the code, not to exempt it.

- **No DRF in any environment the suite runs in.** The kernel exists for
  dispatch without it, and the `floor` job's install-alone step asserts the
  same thing from outside.
- **Where several checks can answer one input, size the test so the one it
  names is the one that answers**, and assert which message came back.
- **A multi-condition guard is one branch arc.** Name, beside the guard, the
  test that fails without each condition.

## Type checking

`ty`, scoped to `django_spec_cli` via `[tool.ty.environment]`. The package
ships `py.typed`, so consumers get the annotations.

Never a mypy-style `# type: ignore` in the package - a pre-commit hook rejects
it.

## Linting and formatting

`ruff` is the source of truth for both. Use `...` rather than `pass` for empty
bodies.

`make lint` does **not** run `ruff format --check`, and CI does. Run
`uv run ruff format --check` before pushing.

## Imports inside the package

Absolute and fully qualified, never relative - `ban-relative-imports = "all"` is
configured and enforced. isort order is stdlib, third party, first party.

`from __future__ import annotations` goes at the top of every annotated file;
`required-imports` enforces it, and re-export `__init__.py` files are exempt.

## Compatibility floor

| | Minimum | Tested against |
| --- | --- | --- |
| Python | 3.10 | 3.10 through 3.14 |
| Django | 4.2 | 4.2, 5.0, 5.1, 5.2, 6.0, 6.1 |
| django-service-specs | 0.11.0 | the newest release, and the floor in the `floor` job |

The Python and Django floors are the kernel's, and cannot sit below them.

## CI and pre-commit

Seven jobs in `tests.yml`: `lint`, `docs`, `floor` (resolves every declared
dependency at the bottom of its window and runs the suite there), `test` (the
Python x Django matrix), `coverage-badge`, `secrets`, and the `tests-passed`
gate that branch protection points at. `upstream-drift.yml` resolves the newest
versions `pyproject.toml` allows on a schedule, which is how a kernel release
that breaks this package is found.

Pre-commit runs gitleaks, the standard hygiene hooks, ruff, ty, four convention
guards (no local filesystem paths, no internal plan-step labels, no mypy-style
type-ignore, no emoji or marker glyphs in any committed file) and
`check-changelog`, which refuses a changelog a merge or rebase has silently
rearranged.

## Releasing

```
make release-bump VERSION=X.Y.Z   # rewrites version.py, promotes the changelog
# edit CHANGELOG.md to fill in the new section, review the diff
# open a PR, get it reviewed, merge to main
```

Releases are **main-triggered**. The release job on `main` short-circuits to a
no-op when a `vX.Y.Z` tag for the version in source already exists on origin,
so an ordinary merge costs nothing. That guard is why the tag list starts at
`v0.0.0`, a version never published: a repository with no tags reads its
version as unreleased on the first push to `main` and runs a real release
attempt. `0.1.0` is the first version on PyPI.

Publishing goes through a PyPI Trusted Publisher that names this repo, the
workflow `release.yml` and the environment `pypi`. It lives on PyPI rather than
in a checkout, so renaming that workflow file or that environment breaks the
next release and nothing here fails first.
