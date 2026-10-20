"""A registry served as a management command, and a command that looks its user up by username.

``tests/docs/test_commands_examples.py`` runs every command line
``docs/index.md`` shows through this module's ``Command``, from argv as
``manage.py`` would, and asserts the output and exit status printed beside
it, so the page cannot show a run the command does not produce.

The two note specs above the page's markers are the kernel's own documentation
examples, a selector and a write, declared here so this site's examples import
nothing from another repository's docs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django_service_specs import (
    DataclassPresenter,
    DataclassValidator,
    FieldMarking,
    Parameter,
    Parameters,
    PermissionCheck,
    PrincipalUnavailable,
    SelectorKind,
    SelectorSpec,
    ServiceSpec,
    SpecRegistry,
    Unrestricted,
)

from django_spec_cli import SpecCommand
from tests.dispatch_app.models import Note


class IsSignedIn(PermissionCheck):
    def has_permission(self, principal: Any, spec: Any) -> bool:
        return principal.is_authenticated


@dataclass
class NoteRow:
    id: Annotated[int, FieldMarking.handle()]
    title: Annotated[str, FieldMarking.label()]


def notes_of(*, user: Any, search: str = "", ordering: str = "title") -> QuerySet[Note]:
    return Note.objects.filter(owner=user, title__icontains=search).order_by(ordering)


list_notes_spec = SelectorSpec(
    kind=SelectorKind.LIST,
    selector=notes_of,
    permissions=[IsSignedIn()],
    reads=Parameters.of(
        Parameter("search", "string", help="Part of the title, in any case."),
        Parameter("ordering", "string", choices=["title", "-title"], default="title"),
    ),
    select_related=["owner"],
    presenter=DataclassPresenter(NoteRow),
)


@dataclass
class Rename:
    title: str


@dataclass
class NoteOut:
    id: int
    title: str


class IsOwner(PermissionCheck):
    message = "Only the note's owner may rename it."

    def has_permission(self, principal: Any, spec: Any) -> bool:
        return principal.is_authenticated

    def has_object_permission(self, principal: Any, spec: Any, target: Any) -> bool:
        return target.owner_id == principal.pk


def rename_note(*, instance: Note, title: str) -> Note:
    instance.title = title
    instance.save(update_fields=["title"])
    return instance


rename_note_spec = ServiceSpec(
    service=rename_note,
    permissions=[IsOwner()],
    validator=DataclassValidator(Rename),
    instance_selector_spec=SelectorSpec(
        kind=SelectorKind.RETRIEVE,
        selector=lambda *, pk: Note.objects.filter(pk=pk),
        reads=Parameters.of(Parameter("pk", "integer", required=True)),
    ),
    presenter=DataclassPresenter(NoteOut),
)


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
