"""A registry of specs as a management command."""

from django_spec_cli.argv.add_spec_arguments import add_spec_arguments
from django_spec_cli.argv.describe_parameters import describe_parameters
from django_spec_cli.argv.parameter_descriptor import ParameterDescriptor
from django_spec_cli.argv.parsed_arguments import parsed_arguments
from django_spec_cli.exit_code_for import exit_code_for
from django_spec_cli.render.render_json_lines import render_json_lines
from django_spec_cli.render.render_result import render_result
from django_spec_cli.render.render_table import render_table
from django_spec_cli.render.wants_table import wants_table
from django_spec_cli.report.unguarded_message import unguarded_message
from django_spec_cli.spec_command import SpecCommand
from django_spec_cli.types.exit_code import ExitCode
from django_spec_cli.version import __version__

__all__ = [
    "__version__",
    "ExitCode",
    "ParameterDescriptor",
    "SpecCommand",
    "exit_code_for",
    "render_json_lines",
    "render_result",
    "render_table",
    "wants_table",
    "add_spec_arguments",
    "describe_parameters",
    "parsed_arguments",
    "unguarded_message",
]
