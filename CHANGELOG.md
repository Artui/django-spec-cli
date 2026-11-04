# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] — 2026-11-04

### Changed
- **The kernel floor is `django-service-specs>=0.25.0`, the first kernel
  release that keeps a read a provider requires itself demanded of the
  caller.** From 0.3.1 `--help` reads its options, and which are marked
  `(required)`, from the kernel's `spec_caller_input_schema`, so it repeats
  what the installed kernel answers. On kernel 0.24.x a read declared
  required that a `kwargs` provider takes by name with no default, such as
  `def needs_project(*, project: int)`, was offered without `(required)`, and
  a run leaving it out crashed in the provider with a `TypeError`. From 0.25.0
  it is marked `(required)`, and that run is refused as invalid arguments,
  exit code 3. The lowest-declared-versions job runs the suite on 0.25.0.

## [0.3.1] — 2026-11-04

### Fixed
- **`--help` offers and requires what dispatch asks a caller for.** A
  subcommand's options, and which of them are marked `(required)`, are now
  read from the kernel's `spec_caller_input_schema` under the command's
  `pool_seeds`, rather than from `server_owned_keys` read without them. On any
  kernel from 0.15.0, two parameters were shown wrongly. A read declared
  required beside a provider that may fill it, such as a `kwargs` provider
  whose return names no keys, was marked `(required)`, though a run leaving
  it out was dispatched. A `reflected` read named like a seed the command's
  `pool_seeds` registers was offered as an option and marked `(required)`,
  and passing it was refused as an unknown argument, exit code 3. It is no
  longer an option. No public name changes.

## [0.3.0] — 2026-11-04

### Changed
- **The kernel floor is `django-service-specs>=0.24.0`, the first kernel
  release with `PermissionCheckDenied` in `REFUSALS`.** The kernel raises it,
  a subclass of `NotPermitted`, when a permission check the spec declares
  answers `False`. A run it refuses still exits `NOT_PERMITTED`, through the
  `NotPermitted` row, as it did on every earlier kernel, so no exit code
  changes. The test holding the exit codes against the kernel's list now
  decides that refusal's code by name, and the lowest-declared-versions job
  runs the suite on 0.24.0.

## [0.2.1] — 2026-10-21

### Fixed
- **The documentation names the right packages.** The site description said the
  command runs a django-spec-cli registry, where the registry is
  django-service-specs'; the `SpecCommand` docstring and the index page compared
  `pool_seeds` to `SpecView`'s as if the kernel still shipped it, where it now
  lives in django-spec-html; and the README's LICENSE links were relative, which
  break on PyPI. No code changes.

## [0.2.0] — 2026-10-20

### Changed
- **The kernel floor is `django-service-specs>=0.11.0`, the first kernel
  release without its own copy of the command.** Below it the kernel still
  shipped `django_service_specs.commands` and registered its own `W001` and
  `W003` over its own `SpecCommand`, so a project listing both
  `"django_service_specs"` and `"django_spec_cli"` saw each id for the
  commands subclassing its own class, and a command that could not be loaded
  was reported under both. From 0.11.0 the kernel's app registers no check, so
  a project that still lists `"django_service_specs"` sees nothing from it, and
  the checks are reported once, under `django_spec_cli.`, by listing
  `"django_spec_cli"`.

## [0.1.0] — 2026-10-20

### Added
- **`django-spec-cli`: a `django-service-specs` registry served as a management
  command, the kernel's command half moved out.** This is the kernel's
  `commands/` subpackage as it shipped in `django-service-specs` 0.10.0, with
  its history, tests and documentation page, so the kernel can carry no
  transport. `SpecCommand` serves one subcommand per spec, with an option for
  each parameter, the principal named by `--as-user`, the result as a table or
  JSON Lines, `--explain` for the specs that authorize nothing, and an
  `ExitCode` for every refusal; `exit_code_for`, the `render_*` functions,
  `wants_table`, the argv helpers and `unguarded_message` come with it. The
  command line, the exit codes and the subclass contract are unchanged; the
  import path is `django_spec_cli`, the output setting is `SPEC_CLI_OUTPUT`
  (the values the kernel's `SERVICE_SPECS_COMMAND_OUTPUT` took), and the system
  checks are `django_spec_cli.W001` and `W003`, registered by listing
  `"django_spec_cli"` in `INSTALLED_APPS`. Until the kernel removes its own copy,
  kernel 0.10.x still registers `django_service_specs.W001` and `W003` over its
  own `SpecCommand`, so a project listing both apps sees both ids, each for the
  commands subclassing its own class, and a command that cannot be loaded is
  reported by each. Floors: Python 3.10, Django 4.2 and
  `django-service-specs>=0.10.0`, the first kernel release with every name the
  command reads at its root.

[Unreleased]: https://github.com/Artui/django-spec-cli/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/Artui/django-spec-cli/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/Artui/django-spec-cli/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/Artui/django-spec-cli/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/Artui/django-spec-cli/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Artui/django-spec-cli/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Artui/django-spec-cli/compare/v0.0.0...v0.1.0
