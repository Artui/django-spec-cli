from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from django_service_specs import UNSET, refusal_messages
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Input, Select, Static, Switch, TextArea

from django_spec_cli.argv.parameter_descriptor import ParameterDescriptor
from django_spec_cli.render.utils import compact_json


class ParameterFields(Vertical):
    """A field per sendable parameter, read back as the flat values ``coerce_flat`` takes.

    An untouched field sends nothing, and a ``bound`` one is shown read-only and left out of it."""

    DEFAULT_CSS = """
    ParameterFields { height: auto; }
    ParameterFields .refusal { color: $error; }
    ParameterFields TextArea { height: 4; }
    """

    def __init__(
        self,
        descriptors: Sequence[ParameterDescriptor],
        *,
        bound: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.bound = dict(bound or {})
        self.descriptors = tuple(d for d in descriptors if d.argv)
        self.unsendable = tuple(
            d.name for d in descriptors if not d.argv and d.name not in self.bound
        )
        self._toggled: set[str] = set()

    def compose(self) -> ComposeResult:
        for descriptor in self.descriptors:
            yield Static(_label(descriptor))
            if descriptor.name in self.bound:
                yield _bound_field(descriptor.name, self.bound[descriptor.name])
            else:
                yield _field(descriptor)
            yield Static(classes="refusal", id=f"refusal-{descriptor.name}")
        if self.unsendable:
            names = ", ".join(self.unsendable)
            yield Static(Text(f"Takes arguments this screen cannot send: {names}."))

    def on_switch_changed(self, event: Switch.Changed) -> None:
        self._toggled.add(str(event.switch.name))

    def values(self) -> dict[str, Any]:
        """What the operator filled in, by parameter name, each as a flat transport spells it."""
        found: dict[str, Any] = {}
        for descriptor in self.descriptors:
            if descriptor.name in self.bound:
                continue
            value = self._value(descriptor.name, self.query_one(f"#field-{descriptor.name}"))
            if value is not None:
                found[descriptor.name] = value
        return found

    def _value(self, name: str, field: Widget) -> Any:
        if isinstance(field, Switch):
            return str(field.value).lower() if name in self._toggled else None
        if isinstance(field, Select):
            return None if field.value is Select.NULL else field.value
        if isinstance(field, TextArea):
            lines = [line.strip() for line in field.text.splitlines() if line.strip()]
            return lines or None
        return cast("Input", field).value or None

    def show_refusals(self, detail: Any) -> list[str]:
        """Place each message in ``detail`` below its field; return those that name none."""
        placed: dict[str, list[str]] = {d.name: [] for d in self.descriptors}
        rest: list[str] = []
        for path, text in refusal_messages(detail):
            if (path[0] if path else None) in placed:
                inner = ".".join(path[1:])
                placed[path[0]].append(f"{inner}: {text}" if inner else text)
            else:
                rest.append(f"{'.'.join(path)}: {text}" if path else text)
        for name, messages in placed.items():
            self.query_one(f"#refusal-{name}", Static).update(Text("\n".join(messages)))
        return rest


def _label(descriptor: ParameterDescriptor) -> Text:
    label = Text.assemble((descriptor.name, "bold"), f"  {descriptor.type}")
    if descriptor.items is not None:
        label.append(f" of {descriptor.items}, one per line")
    if descriptor.required:
        label.append("  (required)")
    if descriptor.help:
        label.append(f"\n{descriptor.help}", "dim")
    return label


def _bound_field(name: str, value: Any) -> Widget:
    shown = value if isinstance(value, str) else compact_json(value)
    return Input(shown, id=f"field-{name}", disabled=True)


def _field(descriptor: ParameterDescriptor) -> Widget:
    field_id = f"field-{descriptor.name}"
    if descriptor.choices is not None:
        labels = dict(descriptor.choice_labels or ())
        options = [(Text(str(labels.get(c, c))), c) for c in descriptor.choices]
        return Select(options, id=field_id, prompt="(not sent)")
    if descriptor.type == "boolean":
        return Switch(id=field_id, name=descriptor.name)
    if descriptor.type == "array":
        return TextArea(id=field_id)
    shown = "" if descriptor.default is UNSET else f"default {compact_json(descriptor.default)}"
    return Input(id=field_id, placeholder=shown)
