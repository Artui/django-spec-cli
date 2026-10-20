# API reference

Everything below is exported from `django_spec_cli` directly, and from the
subpackage it is listed under. Import from the package root in application
code; the subpackage paths are where each name is defined. Kernel names the
command reads - `SpecRegistry`, `dispatch`, the refusals - are documented on
[the kernel's site](https://artui.github.io/django-service-specs/reference/).

## Settings

One Django setting, read at the call rather than at import, so
`override_settings` reaches a command built before it.

- **`SPEC_CLI_OUTPUT`**: the format a `SpecCommand` writes its result in.
  `"auto"` when unset, a table on a terminal and JSON Lines on anything else;
  `"table"` or `"json"` pins one project-wide, and a command's own `--table`
  or `--json` still wins. Anything else, a different case included, is
  refused as `ImproperlyConfigured` where it is read. See
  [`wants_table`][django_spec_cli.render.wants_table.wants_table].

## System checks

Registered by `DjangoSpecCliConfig`, so a project gets them by listing
`"django_spec_cli"` in `INSTALLED_APPS`.

- **`django_spec_cli.W001`**: a spec a `SpecCommand` serves authorizes
  nothing, every permission check it declares being `Unrestricted`. Once per
  open spec, worded by
  [`unguarded_message`][django_spec_cli.report.unguarded_message.unguarded_message].
- **`django_spec_cli.W003`**: a command could not be loaded to be checked.

## The command

::: django_spec_cli.spec_command.SpecCommand
::: django_spec_cli.exit_code_for.exit_code_for

## Rendering a result

::: django_spec_cli.render.render_result.render_result
::: django_spec_cli.render.render_table.render_table
::: django_spec_cli.render.render_json_lines.render_json_lines
::: django_spec_cli.render.wants_table.wants_table

## Parameters as options

::: django_spec_cli.argv.describe_parameters.describe_parameters
::: django_spec_cli.argv.parameter_descriptor.ParameterDescriptor
::: django_spec_cli.argv.add_spec_arguments.add_spec_arguments
::: django_spec_cli.argv.parsed_arguments.parsed_arguments

## Reporting open specs

::: django_spec_cli.report.unguarded_message.unguarded_message

## Types

::: django_spec_cli.types.exit_code.ExitCode
