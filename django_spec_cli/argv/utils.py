"""Helpers the command modules share: how a parameter's name becomes argv and back."""

from __future__ import annotations

DESTINATION_PREFIX = "spec_arg__"
"""Where a spec argument lands in argparse's namespace.

A spec parameter may be named ``verbosity``, ``settings`` or ``traceback``, and
``BaseCommand`` keeps its own options in the same namespace under exactly those
names. Prefixed, the two never meet, so a spec argument cannot change how the
command itself runs. ``parsed_arguments`` is the only reader."""


def destination(name: str) -> str:
    """The namespace attribute a parameter's option stores its value under."""
    return DESTINATION_PREFIX + name


def option_string(name: str) -> str:
    """The option a parameter is sent with: ``due_at`` is ``--due-at``."""
    return "--" + name.replace("_", "-")
