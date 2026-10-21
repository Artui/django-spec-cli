# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/Artui/django-spec-cli/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Artui/django-spec-cli/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Artui/django-spec-cli/compare/v0.0.0...v0.1.0
