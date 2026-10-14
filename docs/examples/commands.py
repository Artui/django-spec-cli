"""A registry served as a management command, and a command that looks its user up by username.

``tests/docs/test_commands_examples.py`` runs every command line
``docs/commands.md`` shows through this module's ``Command``, from argv as
``manage.py`` would, and asserts the output and exit status printed beside
it, so the page cannot show a run the command does not produce.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model

from django_service_specs import (
    PrincipalUnavailable,
    ServiceSpec,
    SpecCommand,
    SpecRegistry,
    Unrestricted,
)
from docs.examples.declaring import list_notes_spec
from docs.examples.quickstart import rename_note_spec


# --8<-- [start:command]
def whoami(*, user: Any) -> str:
    """The username of the user the command runs as."""
    return user.get_username()


notes = SpecRegistry()
notes.register("rename_note", rename_note_spec)
notes.register("list_notes", list_notes_spec)
notes.register("whoami", ServiceSpec(service=whoami, permissions=[Unrestricted()]))


# yourapp/management/commands/notes.py
class Command(SpecCommand):
    registry = notes


# --8<-- [end:command]


# --8<-- [start:by_username]
class ByUsername(SpecCommand):
    registry = notes

    def resolve_as_user(self, value: str) -> Any:
        users = get_user_model()
        try:
            return users.objects.get(username=value)
        except users.DoesNotExist:
            raise PrincipalUnavailable(f"No user named {value!r}.") from None


# --8<-- [end:by_username]
