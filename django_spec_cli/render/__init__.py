"""How a command writes a presented result: a table for a terminal, JSON lines for a pipe."""

from django_spec_cli.render.render_json_lines import render_json_lines
from django_spec_cli.render.render_result import render_result
from django_spec_cli.render.render_table import render_table
from django_spec_cli.render.wants_table import wants_table

__all__ = [
    "render_json_lines",
    "render_result",
    "render_table",
    "wants_table",
]
