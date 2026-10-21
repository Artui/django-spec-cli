# django-spec-cli

[![CI](https://github.com/Artui/django-spec-cli/workflows/tests/badge.svg)](https://github.com/Artui/django-spec-cli/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/django-spec-cli.svg)](https://pypi.org/project/django-spec-cli/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-spec-cli.svg)](https://pypi.org/project/django-spec-cli/)
[![Django versions](https://img.shields.io/pypi/djversions/django-spec-cli.svg)](https://pypi.org/project/django-spec-cli/)
[![Docs](https://img.shields.io/badge/docs-artui.github.io-blue.svg)](https://artui.github.io/django-spec-cli/)
[![Coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Artui/django-spec-cli/gh-pages/coverage.json)](https://github.com/Artui/django-spec-cli/actions/workflows/tests.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/pypi/l/django-spec-cli.svg)](https://github.com/Artui/django-spec-cli/blob/main/LICENSE)

Run a [`django-service-specs`](https://github.com/Artui/django-service-specs)
registry from `manage.py`: one subcommand per spec, an option for each of its
parameters, a principal named on the command line, and an exit code for every
refusal.

It is the kernel's management-command transport, moved out of the kernel with
its history so the kernel carries no transport. The command line, the exit
codes and the `SpecCommand` subclass contract are the ones the kernel shipped;
the import path, the system check ids and the setting key are this package's.

## Install

```bash
pip install django-spec-cli
```

Python 3.10 or later, Django 4.2 or later, and `django-service-specs` 0.11.0 or
later, which it installs.

## Quickstart

Subclass `SpecCommand` in one of your apps' `management/commands/` modules and
name a registry; the module's name is the command's:

```python
# yourapp/management/commands/notes.py
from django_spec_cli import SpecCommand

from yourapp.specs import notes  # a django_service_specs.SpecRegistry


class Command(SpecCommand):
    registry = notes
```

```console
$ python manage.py notes rename-note --as-user 1 --pk 1 --title Final --json
{"id":1,"title":"Final"}
```

The run goes through the kernel's `dispatch`, so the permission checks are
enforced for the user `--as-user` names. `--explain` lists the specs that
authorize nothing.

## The system check

List `"django_spec_cli"` in `INSTALLED_APPS` and `manage.py check` reports
every open spec a `SpecCommand` serves as `django_spec_cli.W001`, and a command
that could not be loaded as `django_spec_cli.W003`. The command itself needs no
app listed.

The kernel keeps no check of its own: its app registers nothing, so a project
listing only `"django_service_specs"` gets no check for a command. List
`"django_spec_cli"`.

## Documentation

<https://artui.github.io/django-spec-cli/>

## License

MIT. See [LICENSE](https://github.com/Artui/django-spec-cli/blob/main/LICENSE).
