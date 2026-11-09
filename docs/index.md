# Running operations from the command line

[`SpecCommand`][django_spec_cli.spec_command.SpecCommand] serves
every spec in a [registry](https://artui.github.io/django-service-specs/registry/) as one management command, with one
subcommand per spec. An operator runs an operation as a named user, with
arguments as options, and gets its presented result as a table or as JSON
Lines:

```console
$ python manage.py notes rename-note --as-user 1 --pk 1 --title Final --json
{"id":1,"title":"Final"}
```

The run goes through [`dispatch`](https://artui.github.io/django-service-specs/dispatching/) as every other transport's
does: the same shape check and Validator, the same permission checks, enforced,
for the user `--as-user` names, the same presenter. It needs Django and
nothing else.

```python
from django_spec_cli import ExitCode, SpecCommand, exit_code_for
```

## Installing

```bash
pip install django-spec-cli
```

It installs [`django-service-specs`](https://artui.github.io/django-service-specs/), the kernel whose specs it serves,
from 0.30.0, on Python 3.10 and Django 4.2 or later. The command line was the
kernel's `commands/` subpackage, and moved here so the kernel carries no
transport.

## What it is not

**The command is not an authorization boundary.** Whoever can run
`manage.py` can already run any code the project can, open `manage.py shell`,
and name any user they like with `--as-user`. What the command offers is
mistake prevention and attribution: every run is made as a named user, is
checked against the permissions that user holds, and records that user
wherever the operation records who acted. Refusing to run an open spec would
stop nobody, so the command [reports](#open-specs-explain) open specs instead.

## Declaring a command

A project declares the command by subclassing, in one of its own apps'
`management/commands/` modules, and names the registry. The module's name is
the command's:

```python
--8<--
docs/examples/commands.py:command
--8<--
```

One project can serve two registries as two commands, each with its own name.
The registry is read when the command's parser is built, on every run; a
command naming none is refused then with `ImproperlyConfigured`, as is a
registry where two names would be one subcommand (`a_b` and `a-b`).

A registry whose callables read a seed of their own - an affordance's `when`,
a selector - names the seeds on the class, as
[django-spec-html's `SpecView`](https://artui.github.io/django-spec-html/http/#the-class-form)
does:
`pool_seeds = DEFAULT_POOL_SEEDS.extend(tenant=current_tenant)`. Without it a
callable asking for a seed nobody registered fails as it would in `dispatch`.

The command does not need `django_spec_cli` or `django_service_specs` in
`INSTALLED_APPS`. Listing `django_spec_cli` adds the
[system check](#open-specs-explain).

## Subcommands and their options

Each registry entry is a subcommand named after it, with each `_` shown as
`-`: `rename_note` is `rename-note`. Its options are the spec's
[parameters](https://artui.github.io/django-service-specs/arguments/), spelled by
[`add_spec_arguments`][django_spec_cli.argv.add_spec_arguments.add_spec_arguments]:
`--due-at` for `due_at`, a `--flag`/`--no-flag` pair for a boolean, and an
array as a repeated option, `--tag a --tag b`. Every value reaches
[`coerce_flat`][django_service_specs.parameters.coerce_flat.coerce_flat] as
the string typed, and is refused as a query string's would be. A value that
starts with `-` is read by argparse as an option, so it is attached with an
equals sign: `--tag=-x`.

`manage.py notes --help` lists the subcommands, each with the first paragraph
of its service's or selector's docstring and whether it reads or writes, or
its registered name when the function says nothing. `manage.py notes
rename-note --help` lists its options, with `(required)` where leaving one
out is refused. Both are read from the input schema a transport advertises,
[`spec_caller_input_schema`][django_service_specs.schema.spec_caller_input_schema.spec_caller_input_schema],
under the command's `pool_seeds`, so the command asks for what dispatch asks
for. On a `partial` spec, `(required)` is only what names the row: the
Validator's fields may be left out, as dispatch allows. A parameter a provider
may fill, such as a read beside a `kwargs` provider whose return names no keys,
is an option and is not required, unless the provider takes that read by name
with no default: only the caller can fill it then, so a read declared required
stays `(required)`.

Some parameters have no option:

- **A key the server fills**: one a `kwargs` provider is annotated to answer,
  since a value sent for it would be dropped, and a `reflected` read named like
  a seed `pool_seeds` registers, since the seed fills it and dispatch refuses an
  argument of its name.
- **A parameter with no flat spelling**: an object, an array of objects or of
  arrays, and a file. The subcommand's help names them. A spec that requires
  one, such as any `many` spec, cannot be run from the command line.

No option is matched by a prefix. Argparse reads `--titl` as `--title` by
default, and beside a parameter `as_user_id` a mistyped `--as-user-i 7` would
have been read as that parameter rather than refused. Here every prefix is
refused, Django's own options' included.

A spec parameter may not map to an option the command owns: `--as-user`,
`--json`, `--table`, or one of Django's, such as `--verbosity` or
`--settings`. `manage.py` reads `--settings` from anywhere on the line, so a
spec option of that name would configure Django instead. Such a parameter is
refused with `ImproperlyConfigured` when the parser is built.

## The user a run is made as

`--as-user` is required. There is no default user, no system user of the
command's own, and no fallback to an anonymous user. Its value goes through
the command's
[`resolve_as_user`][django_spec_cli.spec_command.SpecCommand.resolve_as_user]
method, which by default looks a user up by primary key with
[`resolve_principal`][django_service_specs.authorization.resolve_principal.resolve_principal].
A project whose runbooks name people by username overrides the method:

```python
--8<--
docs/examples/commands.py:by_username
--8<--
```

The contract is: return a user, or raise `PrincipalUnavailable`, which ends
the run with exit status 5. Anything else the method raises is a bug in it,
and propagates with its traceback. An override need not refuse a deactivated
user itself, since `dispatch` refuses one whatever the lookup returns.

The command passes no `Grant`, so the spec's permission checks run for that
user as they would for a request from them:

```console
$ python manage.py notes rename-note --as-user 2 --pk 1 --title Final
CommandError: Only the note's owner may rename it.
$ echo $?
4
```

## Output

A run's result goes through the spec's presenter, then is written in one of
two formats, decided in this order:

1. `--table` or `--json` on the command line.
2. The `SPEC_CLI_OUTPUT` setting: `"table"` or `"json"` pins one
   project-wide; `"auto"`, the default, leaves it to the next step.
3. A table when stdout is a terminal, JSON Lines when it is a pipe or a file.

That last step means an interactive run and CI print different things by
default, which is what the flag and the setting are for:

```console
$ python manage.py notes list-notes --as-user 1 --json
{"id":1,"title":"Final"}
{"id":2,"title":"Shopping"}
$ python manage.py notes list-notes --as-user 1 --table
id  title
 1  Final
 2  Shopping
```

The table's columns come from the spec's `Output`, never from the first row;
see [`render_table`][django_spec_cli.render.render_table.render_table]
for what a field's marking does to them. JSON Lines are written one row at a
time, but `present` builds a list result whole before the first row is
written, so a large read is held in memory once, as an HTTP response holds
it. A service that returns nothing writes nothing.

## Exit codes

A refusal ends the run with a `CommandError` whose message goes to stderr and
whose
[`ExitCode`][django_spec_cli.types.exit_code.ExitCode] is the
process's exit status. The codes are a public contract, for a script to
branch on:

| Code | `ExitCode` | The run |
| --- | --- | --- |
| 0 | `SUCCESS` | ran, and its result was written |
| 1 | `ERROR` | failed in a way nobody declared: the traceback is printed |
| 2 | `USAGE` | never started: the command line was malformed |
| 3 | `INVALID_ARGUMENTS` | `InvalidArguments`, `ServiceValidationError`, any other `DispatchError` |
| 4 | `NOT_PERMITTED` | `NotPermitted`, and `PermissionCheckDenied`, a declared check's denial |
| 5 | `PRINCIPAL_UNAVAILABLE` | `PrincipalUnavailable`: no such user, or a deactivated one |
| 6 | `NOT_FOUND` | the row named does not exist, or the service raised `ServiceNotFound` |
| 7 | `CONFLICT` | `ServiceConflict`, and `ActionUnavailable` with its code in the message |
| 8 | `INPUT_REQUIRED` | `AdditionalInputRequired` |
| 9 | `REFUSED` | any other `ServiceError` |

[`exit_code_for`][django_spec_cli.exit_code_for.exit_code_for]
is the mapping, for a project that runs specs from a command of its own.

An invalid argument prints one line per refused field, after its path:

```console
$ python manage.py notes rename-note --as-user 1 --pk 1
CommandError: Invalid arguments.
title: This field is required.
$ echo $?
3
$ python manage.py notes rename-note --as-user 1 --pk one --title Final
CommandError: Invalid arguments.
pk: Enter a whole number.
$ echo $?
3
$ python manage.py notes rename-note --as-user 1 --pk 99 --title Final
CommandError: Not found.
$ echo $?
6
```

A command line cannot ask a question, so `AdditionalInputRequired` ends the
run with code 8 and names the options its `schema` asks for. The operator, or
a script that knows the answer, runs the command again with them.

Through `call_command` the `CommandError` is raised to the caller rather than
printed, with the code as its `returncode`. A malformed command line is a
`CommandError` there too, as Django makes every parser error, with
`returncode` 1 rather than 2.

## Open specs: `--explain` and the system check { #open-specs-explain }

`whoami` is open to every active user, which is what it is for:

```console
$ python manage.py notes whoami --as-user 2 --json
"grace"
```

`--explain` runs no spec. It prints one line for each spec the command serves
that [authorizes nothing](https://artui.github.io/django-service-specs/registry/#open-specs-reported), every check it
declares being `Unrestricted`:

```console
$ python manage.py notes --explain
'whoami' in manage.py notes authorizes nothing: every permission check it declares is Unrestricted, so any active user named by --as-user may run it.
```

Listing `"django_spec_cli"` in `INSTALLED_APPS` reports the same
sentence from `manage.py check`, as `django_spec_cli.W001`, once per
open spec of every `SpecCommand` in the project, and a command that could not
be loaded to be checked as `django_spec_cli.W003`. There is no
`W002`: a spec with an empty `permissions` is refused when it is built, so
none reaches a registry.

`django_spec_cli.W004` reports, once per spec, a declaration the kernel's
[`check_seeds`][django_service_specs.dispatch.check_seeds.check_seeds]
refuses under the command's `pool_seeds`: a keyword the callable requires
that nothing fills, or a read declared optional that a `kwargs` provider
takes by name with no default, among others. A run of that spec is refused
with the same sentence, raised as `ImproperlyConfigured` (exit code 1,
with a traceback) before `--as-user` is looked up, even when the options sent
would let it run. The command's other specs are unaffected.

The same holds for a declaration only the command's own read reaches. A
Validator may declare a field only when `call_transport(call_context) == "cli"`,
and if that field is named for a key dispatch seeds itself, such as `user`,
`check_seeds` (asked outside a call) never sees it, and the read `--help`
makes under the stamped dict raises. That refusal belongs to the one spec: its
subcommand takes no option, its `--help` prints the kernel's reason, a run of it
ends with the same sentence as `ImproperlyConfigured` whatever was sent, and
`django_spec_cli.W004` names it. The command's other specs, `--help` and
`--explain` work as before. A spec both reads refuse is reported once, with the
`check_seeds` reason.

A `Parameter` is optional unless it says `required=True`, so a read declared
plainly over a keyword with no default is one such declaration:

```python
--8<--
docs/examples/commands.py:refused
--8<--
```

`manage.py check` reports it as `django_spec_cli.W004`, and
`manage.py drafts retitle --as-user 1 --title Final` is refused with the same
sentence:

```text
'retitle' in manage.py drafts cannot run as declared, and a run of it is refused: ServiceSpec.service requires the keyword(s) ['title'], declared as optional reads that nothing else fills, so a call leaving one out is refused as missing. Declare the read required, or give the keyword a default.
```

All three are warnings, so a spec nobody runs never stops `migrate`, and
`SILENCED_SYSTEM_CHECKS` silences one by id. Silencing `W004` hides the report
and does not let the spec run.

The kernel keeps no check of its own: its app registers nothing, so a project
listing only `"django_service_specs"` gets no check for a command. List
`"django_spec_cli"`.

A `SpecCommand` keeps Django's system checks on, so on the command line the
report is printed to stderr before every run of every command. The runs on
this page are shown without it; in a project listing the app, each would be
preceded by the warnings for `whoami` and `retitle`. `call_command` skips
system checks for every command but `check`, so a command run through it
does not print them.

## What a callable reads here

Every callable a run reaches is handed one `call_context`, built by the
kernel's
[`build_call_context`][django_service_specs.types.build_call_context.build_call_context]
and stamped last with this package's transport name, the plain string `"cli"`,
exported as `django_spec_cli.CLI_TRANSPORT`. Read it with the kernel's
[`call_transport`][django_service_specs.types.call_transport.call_transport],
or compare `call_context["transport"] == "cli"` with nothing imported:

```python
--8<--
docs/examples/commands.py:transport
--8<--
```

- **One dict per run.** The command builds it ahead of everything it asks of
  a spec and hands the same object to the declaration it reads for the
  options it parses, then to `dispatch`, so a permission check, the
  Validator's `parameters()` and `validate()`, a provider, the service and the
  presenter all read `"cli"` from one dict.
- **The standard entries are there as `None`.** `request`, `view`, `format`
  and `action` are keys of the dict with no value, since a command line has
  none. The kernel hands a callable declaring `request` or `view` `None` for
  such an entry, as it does for a missing one, and `format` and `action` are
  never bound by name, so a spec written for HTTP runs here as it did.
- **`--help` is read under a dict too.** The command builds a stamped dict of
  its own for each spec, and the options come from the kernel's caller schema
  read under it, as the Validator's declaration is. A field a Validator
  declares only when `call_transport(call_context) == "cli"` is an option,
  marked `(required)` where it is required, and one it declares to another
  transport is none.
- **Seams.** The value is not configurable: a subclass cannot change what a
  run stamps. What a subclass can supply is `resolve_as_user`, who the run is
  made as, and `pool_seeds`, which adds a keyword to the pool every callable
  may declare, so an entry a project needs in every call is a seed rather
  than a key of the dict.

## What it does not do

- **No payload file.** Arguments are options; an object or a list of rows has
  none, and there is no `--from-json`.
- **No `--dry-run`.** A run that resolves and validates without running the
  service is not offered.
- **Sync only.** The command dispatches with `dispatch`, never `adispatch`,
  so an `async def` service is run as `dispatch` runs one.
- **No transaction of its own.** A spec's `atomic` is dispatch's to honour.
- **No Typer.** The command is argparse, as `manage.py` is, and needs nothing
  beyond Django.
