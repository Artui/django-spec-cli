# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **`--tui` opens terminal screens over the command's registry.** `manage.py <command>
  --tui --as-user USER` opens a keyboard-driven app, built on Textual and installed with
  the new `tui` extra (`pip install 'django-spec-cli[tui]'`), whose first screen lists
  every spec the command serves with its summary and whether it reads or writes. A spec
  the kernel refuses as declared, which `django_spec_cli.W004` reports, is listed greyed
  with the reason and cannot be chosen. The user is looked up once, through
  `resolve_as_user`, so a project's override applies, and every call the screens make
  goes through `dispatch` as that user, in a worker thread off Textual's event loop.
  Without the extra, `--tui` is refused with a message naming it; with a spec name, with
  `--explain` or without `--as-user`, it is a usage error. `--tui` is added after the
  options a spec may not take are fixed, so a spec with a `tui` parameter keeps its
  own `--tui` option. Nothing imports Textual unless `--tui` is passed.
- **Any spec but a list runs from a form on the `--tui` screens.** Choosing a spec opens
  a field per parameter its subcommand would take: a choice list for declared choices, a
  switch for a boolean, one value per line for an array, and a text field otherwise; a
  parameter no flat transport can send is named instead. A field left untouched sends
  nothing, as an option left off the command line, and every value is read by the
  kernel's `coerce_flat`, so the form and the command line read a value alike. `ctrl+s`
  runs a read; a write runs only on a second `ctrl+s`, and an edit or `esc` cancels it.
  The result shows as the command's `--table` prints it, "Not found." for a missing row
  and "Done." for nothing. A refused argument's message sits below its field, and any
  other refusal reads as the command prints it, markup included, as typed. A spec whose
  result is a file is not run there: the form names the subcommand that writes it.
- **A list selector opens as a paged, filterable table on the `--tui` screens.** Its
  columns and cells are the ones the command's `--table` prints for the same rows: the
  declared output's fields with hidden ones left out, a choice's display, a handle's raw
  value, compact JSON for a nested value. Rows come a page at a time through the
  kernel's `paginate_output`, and the screen says which page of how many and how many
  rows in all; `n` and `p` turn the page, and asking past either end stays on the last
  or first page. `/` moves to a filter bar of the spec's reads, filled like the form's
  fields; `enter` in a field or `ctrl+s` runs the list again with them from page one,
  and a refused value or a refused run leaves the rows, and the filter they came from,
  as they were, with the refusal shown. `r` reloads the page. `enter` on a row opens it
  as JSON, every key it was presented with, hidden fields and `affordances` included.
  A value carrying markup shows as typed, in a cell, a header or the row.
- **A documentation page for the `--tui` screens.** It covers opening them, each screen's
  keys, the second `ctrl+s` a write asks for, and what they do not run, with a screenshot
  of each made by `scripts/tui_screenshots.py` through `App.save_screenshot()`.
- **`refusal_text`** is a new public helper: a kernel refusal as the text the command
  prints for it, each refused field on its own line. The `--tui` form shows refusals
  through it, so both read alike.

## [0.7.0] — 2026-11-14

### Added
- **A spec whose result is a file writes its bytes.** A spec presenting through the
  kernel's `FilePresenter` was presented as JSON Lines, and the encoder refused its
  `FileResult` with a `TypeError`. Its subcommand now writes the file's bytes to
  `--output-file PATH`, an option only a file spec's subcommand takes, or else to
  stdout's binary buffer when stdout is not a terminal. At a terminal without
  `--output-file`, with `--table` or `--json`, with a stdout that takes no bytes, or with
  a `PATH` that is a directory or whose directory does not exist, the run is a usage
  error raised before the user is looked up or the spec is run, so nothing is written.
  `SPEC_CLI_OUTPUT` is not read for it. The file's name, type and length go to stderr;
  the name is never used as a path. The file is read whole before `PATH` is opened, so
  a refused run leaves a file there as it was, and an `allow_none` spec finding
  nothing writes nothing. A file spec the kernel's `file_output` refuses (a `LIST`
  selector, `many`, `returns_many`, presented affordances) is refused as declared, for
  its spec alone, and `django_spec_cli.W004` reports it. `write_file` is the new public
  helper.

### Changed
- **The kernel floor is 0.33.0**, up from 0.30.0, for `FileResult`, `FilePresenter` and
  `file_output`. Two things a selector with a `filter_set` shows change with it, both
  the kernel's (0.31.0): `--help` lists a choice filter's labels beside its values, as
  in `one of: ada (Ada Lovelace)`, since the kernel now hands them on; and on Django
  5.0 or later a named group of choices held in a mapping offers and accepts its
  members, where it offered the group's name and refused a member. A lazy affordance
  reason reaches `ActionUnavailable` as text, as before, and the `QueryDict` a
  `FormValidator` now binds is behind dispatch.
- **`W003` is described as it behaves**: it reports any project command that fails to
  load, since a command that will not import cannot be told apart from a `SpecCommand`.
- **The API reference's docstrings are restored.** The docstrings the reference renders
  carry their full text again.
- **The guide states four things it left out.** The checks carry no tag, so a run
  selecting by `--tag` skips them; finding the commands imports every command module
  of the project's apps on each check run; a table hides a hidden field and JSON Lines
  does not; and a table holds its whole result in memory.

## [0.6.0] — 2026-11-09

### Fixed
- **A field a Validator declares only under `cli` is an option.** The command
  asked the kernel's `spec_caller_input_schema` for the options to offer with no
  `call_context`, so the schema was the declaration made to no transport at all,
  and a field the Validator declares only when
  `call_transport(call_context) == "cli"` got no option. If it was required,
  every run was refused for it. The schema is now read under the same stamped
  dict `--help` already hands the Validator, so such a field is offered, marked
  `(required)` where it is, and a run leaving it out is refused with the shape
  check's own message. A field declared to another transport is still no option.
  The command line page no longer carries the caveat that asked for such a field
  to be declared to every transport.

- **A field a Validator declares only under `cli` that dispatch seeds itself is
  refused for its spec alone.** The read `--help` makes under the stamped dict
  raised `ImproperlyConfigured` for such a field, for example `user`, while the
  parser was built, so every spec of the command, `--help` and `--explain` died
  with a traceback, and `django_spec_cli.W004` said nothing because
  `check_seeds` takes no `call_context`. The parser now takes that refusal for
  the one spec: its subcommand takes no option and its `--help` prints the
  kernel's reason, a run of it raises the same sentence as `ImproperlyConfigured`
  before `--as-user` is looked up, whatever was sent, and `W004` names it. The
  command's other specs are unaffected.

### Changed
- **The floor on `django-service-specs` rises from 0.29.0 to 0.30.0**, the
  release that lets `spec_caller_input_schema` take a `call_context`. A project
  on an older kernel stays on 0.5.x.

## [0.5.0] — 2026-11-08

### Added
- **A run stamps its transport: `"cli"`.** Every callable a `SpecCommand` run
  reaches is now handed a `call_context` built by the kernel's
  `build_call_context` and stamped last with `"cli"`, exported as
  `CLI_TRANSPORT`, so a permission check, the Validator, a provider, the
  service and the presenter read `call_transport(call_context) == "cli"` from
  one dict. Before, the command handed `dispatch` none, and a callable reading
  the key saw a missing one, which the kernel reads as an in-process caller.
  The Validator's declaration the command reads for the options it parses is
  asked under the stamped dict as well. `request`, `view`, `format` and
  `action` are in the dict as `None`, which binds nothing different from a
  missing key. The command line page says what a callable reads here.

### Changed
- **The floor on `django-service-specs` rises from 0.25.0 to 0.29.0**, the
  release that adds `build_call_context` and removes the shared `Transport`
  enum. A project on an older kernel stays on 0.4.x.

## [0.4.1] — 2026-11-04

### Added
- **The command line page shows a spec the kernel refuses.** Its system-check
  section now includes an example command, `drafts`, serving one spec that
  declares a plain `Parameter` over a keyword with no default, and prints the
  `django_spec_cli.W004` sentence it gets. The page's tests assert that
  `manage.py check` reports exactly that warning for the example and that a
  run of the spec raises the same sentence, so the page cannot drift from
  what the check and the command say. No change to the package.

## [0.4.0] — 2026-11-04

### Added
- **A spec the kernel refuses as declared is reported, and never run.**
  Every spec a `SpecCommand` serves is now put to the kernel's `check_seeds`
  under the command's `pool_seeds`, which other transports already ask where
  they register a spec. `manage.py check` reports each spec it refuses as
  `django_spec_cli.W004`, a warning, naming the command, the spec and the
  kernel's reason. A run of such a spec raises `ImproperlyConfigured` with the
  same sentence, exit code 1 with a traceback, before `--as-user` is looked
  up. The command's other specs, its `--help` and its `--explain` are
  unaffected.

  Three of the kernel's refusals stop runs that succeeded before, because
  each fails only some calls. The first is a read declared without
  `required=True`, which is `Parameter`'s default, over a keyword the
  service, the selector or a callable such as a `kwargs` provider takes by
  name with no default: `Parameter("title", "string")` over
  `def rename(*, title)`, or `def needs_project(*, project: int)` as the
  provider. A run sending the read worked, and one leaving it out was refused
  as missing or crashed with the provider's `TypeError`; now every run is
  refused, so declare such a read `required=True` or give the keyword a
  default. The second is an array read declaring no `items` over a keyword
  annotated with its element, such as `pks: list[int]`, which was handed the
  command line's strings. The third is a `progress_reporter` requiring a
  keyword nothing fills, which a run whose service never reports never
  called. The others refuse a declaration on which every run that reached
  the callable already failed, with its `TypeError` or the kernel's own
  `ImproperlyConfigured`, which now names the spec and the command.

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

[Unreleased]: https://github.com/Artui/django-spec-cli/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/Artui/django-spec-cli/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/Artui/django-spec-cli/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/Artui/django-spec-cli/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/Artui/django-spec-cli/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/Artui/django-spec-cli/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/Artui/django-spec-cli/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/Artui/django-spec-cli/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/Artui/django-spec-cli/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Artui/django-spec-cli/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Artui/django-spec-cli/compare/v0.0.0...v0.1.0
