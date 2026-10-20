# django-spec-cli

[![CI](https://github.com/Artui/django-spec-cli/workflows/tests/badge.svg)](https://github.com/Artui/django-spec-cli/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/django-spec-cli.svg)](https://pypi.org/project/django-spec-cli/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-spec-cli.svg)](https://pypi.org/project/django-spec-cli/)
[![Django versions](https://img.shields.io/pypi/djversions/django-spec-cli.svg)](https://pypi.org/project/django-spec-cli/)
[![Docs](https://img.shields.io/badge/docs-artui.github.io-blue.svg)](https://artui.github.io/django-spec-cli/)
[![Coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Artui/django-spec-cli/gh-pages/coverage.json)](https://github.com/Artui/django-spec-cli/actions/workflows/tests.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/pypi/l/django-spec-cli.svg)](LICENSE)

Run a [`django-service-specs`](https://github.com/Artui/django-service-specs)
registry from `manage.py`: one subcommand per spec, an option for each of its
parameters, a principal named on the command line, and an exit code for every
refusal.

It is the kernel's management-command transport, moved into a package of its own
so the kernel carries no transport. Documentation:
<https://artui.github.io/django-spec-cli/>.
