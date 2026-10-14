"""How a spec's parameters become command-line options, and come back as its arguments."""

from django_service_specs.commands.argv.add_spec_arguments import add_spec_arguments
from django_service_specs.commands.argv.describe_parameters import describe_parameters
from django_service_specs.commands.argv.parameter_descriptor import ParameterDescriptor
from django_service_specs.commands.argv.parsed_arguments import parsed_arguments

__all__ = [
    "ParameterDescriptor",
    "add_spec_arguments",
    "describe_parameters",
    "parsed_arguments",
]
