"""A ``SpecCommand`` over a registry of note operations, one per shape the command tells apart.

A write that acts on a row (``rename_note``), a read that lists
(``list_notes``), a write echoing every flat type a command line spells
(``schedule``), one raising each refusal a service can (``refuse``), a spec
declared ``partial``, one any active user may run, and one declared by a
``SpecSource``, so ``kernel_spec`` is what the command reads.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Literal

from django import forms
from django.db.models import QuerySet

from django_service_specs.adapters.dataclass.dataclass_presenter import DataclassPresenter
from django_service_specs.adapters.dataclass.dataclass_validator import DataclassValidator
from django_service_specs.adapters.forms.form_validator import FormValidator
from django_service_specs.authorization.permission_check import PermissionCheck
from django_service_specs.authorization.unrestricted import Unrestricted
from django_service_specs.commands.spec_command import SpecCommand
from django_service_specs.parameters.parameters import Parameter, Parameters
from django_service_specs.registry.spec_registry import SpecRegistry
from django_service_specs.services.action_unavailable import ActionUnavailable
from django_service_specs.services.additional_input_required import AdditionalInputRequired
from django_service_specs.services.service_conflict import ServiceConflict
from django_service_specs.services.service_error import ServiceError
from django_service_specs.services.service_not_found import ServiceNotFound
from django_service_specs.services.service_validation_error import ServiceValidationError
from django_service_specs.specs.selector_spec import SelectorSpec
from django_service_specs.specs.service_spec import ServiceSpec
from django_service_specs.types.selector_kind import SelectorKind
from tests.dispatch_app.models import Note


class IsSignedIn(PermissionCheck):
    def has_permission(self, principal: Any, spec: Any) -> bool:
        return bool(principal.is_authenticated)


class IsOwner(IsSignedIn):
    message = "Only the note's owner may change it."

    def has_object_permission(self, principal: Any, spec: Any, target: Any) -> bool:
        return bool(target.owner_id == principal.pk)


@dataclass
class Rename:
    title: str


@dataclass
class NoteOut:
    id: int
    title: str


def rename_note(*, instance: Note, title: str) -> Note:
    """Give a note a new title.

    Only its owner may.
    """
    instance.title = title
    instance.save(update_fields=["title"])
    return instance


def _note_by_pk() -> SelectorSpec:
    return SelectorSpec(
        kind=SelectorKind.RETRIEVE,
        selector=lambda *, pk: Note.objects.filter(pk=pk),
        reads=Parameters.of(Parameter("pk", "integer", required=True)),
    )


rename_note_spec = ServiceSpec(
    service=rename_note,
    permissions=[IsOwner()],
    validator=DataclassValidator(Rename),
    instance_selector_spec=_note_by_pk(),
    presenter=DataclassPresenter(NoteOut),
)


def notes_of(*, user: Any, search: str = "") -> QuerySet[Note]:
    return Note.objects.filter(owner=user, title__icontains=search)


list_notes_spec = SelectorSpec(
    kind=SelectorKind.LIST,
    selector=notes_of,
    permissions=[IsSignedIn()],
    reads=Parameters.of(Parameter("search", "string")),
    presenter=DataclassPresenter(NoteOut),
)


@dataclass
class Schedule:
    due_at: dt.datetime
    urgent: bool = False
    tags: list[str] = field(default_factory=list)
    count: int = 1


def schedule(*, data: Schedule) -> dict[str, Any]:
    return {
        "due_at": data.due_at,
        "offset": str(data.due_at.utcoffset()),
        "urgent": data.urgent,
        "tags": data.tags,
        "count": data.count,
    }


schedule_spec = ServiceSpec(
    service=schedule,
    permissions=[IsSignedIn()],
    validator=DataclassValidator(Schedule),
)


@dataclass
class Refusal:
    kind: Literal[
        "validation",
        "validation_map",
        "validation_list",
        "not_found",
        "conflict",
        "unavailable",
        "input",
        "input_bare",
        "other",
    ]


def refuse(*, kind: str) -> None:
    if kind == "validation":
        raise ServiceValidationError("The title is taken.")
    if kind == "validation_map":
        raise ServiceValidationError(
            {
                "non_field_errors": ["Check the shelf."],
                "title": ["Too long."],
                "books": {"1": {"__all__": ["Missing."], "isbn": ["Malformed."]}},
            }
        )
    if kind == "validation_list":
        raise ServiceValidationError(["First.", "Second."])
    if kind == "not_found":
        raise ServiceNotFound("No such shelf.")
    if kind == "conflict":
        raise ServiceConflict("Already archived.")
    if kind == "unavailable":
        raise ActionUnavailable("The note is archived.", code="archived")
    if kind == "input":
        raise AdditionalInputRequired(
            "40 notes match. Confirm to proceed.", schema={"confirmed": {"type": "boolean"}}
        )
    if kind == "input_bare":
        raise AdditionalInputRequired("Confirm to proceed.")
    raise ServiceError("The shelf is full.")


refuse_spec = ServiceSpec(
    service=refuse, permissions=[IsSignedIn()], validator=DataclassValidator(Refusal)
)


class RetitleForm(forms.Form):
    title = forms.CharField(max_length=100)
    archived = forms.BooleanField(required=False)


def retitle(*, instance: Note, data: dict[str, Any]) -> Note:
    for name, value in data.items():
        setattr(instance, name, value)
    instance.save()
    return instance


retitle_spec = ServiceSpec(
    service=retitle,
    permissions=[IsOwner()],
    validator=FormValidator(RetitleForm),
    instance_selector_spec=_note_by_pk(),
    partial=True,
    presenter=DataclassPresenter(NoteOut),
)


def ping() -> str:
    return "pong"


ping_spec = ServiceSpec(service=ping, permissions=[Unrestricted()])


class MyNotes:
    """A declaration in another library's vocabulary, compiled to a selector spec."""

    def as_kernel_spec(self) -> SelectorSpec:
        return SelectorSpec(
            kind=SelectorKind.LIST,
            selector=notes_of,
            permissions=[IsSignedIn()],
            reads=Parameters.of(Parameter("search", "string")),
            presenter=DataclassPresenter(NoteOut),
        )


registry = SpecRegistry()
registry.register("rename_note", rename_note_spec)
registry.register("list_notes", list_notes_spec)
registry.register("schedule", schedule_spec)
registry.register("refuse", refuse_spec)
registry.register("retitle", retitle_spec)
registry.register("ping", ping_spec)
registry.register("my_notes", MyNotes())


class Command(SpecCommand):
    registry = registry
