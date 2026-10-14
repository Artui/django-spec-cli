"""A registry of specs as a management command."""

from django_service_specs.commands.argv.add_spec_arguments import add_spec_arguments
from django_service_specs.commands.argv.describe_parameters import describe_parameters
from django_service_specs.commands.argv.parameter_descriptor import ParameterDescriptor
from django_service_specs.commands.argv.parsed_arguments import parsed_arguments
from django_service_specs.commands.exit_code_for import exit_code_for
from django_service_specs.commands.render.render_json_lines import render_json_lines
from django_service_specs.commands.render.render_result import render_result
from django_service_specs.commands.render.render_table import render_table
from django_service_specs.commands.render.wants_table import wants_table
from django_service_specs.commands.report.unguarded_message import unguarded_message
from django_service_specs.commands.report.unguarded_spec import UnguardedSpec
from django_service_specs.commands.report.unguarded_specs import unguarded_specs
from django_service_specs.commands.spec_command import SpecCommand

__all__ = [
    "ParameterDescriptor",
    "SpecCommand",
    "exit_code_for",
    "render_json_lines",
    "render_result",
    "render_table",
    "wants_table",
    "UnguardedSpec",
    "add_spec_arguments",
    "describe_parameters",
    "parsed_arguments",
    "unguarded_message",
    "unguarded_specs",
]
