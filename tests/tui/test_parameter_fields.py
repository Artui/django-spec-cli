from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.widgets import Input, Select, Static, Switch, TextArea

from django_spec_cli.argv.parameter_descriptor import ParameterDescriptor
from django_spec_cli.tui.parameter_fields import ParameterFields

MARKUP = "[b]x[/b] [/x]"

DESCRIPTORS = (
    ParameterDescriptor("title", "string", required=True, help=MARKUP),
    ParameterDescriptor("count", "integer", default=1),
    ParameterDescriptor("urgent", "boolean"),
    ParameterDescriptor("tags", "array", items="string"),
    ParameterDescriptor("kind", "string", choices=("a", "b"), choice_labels=(("a", MARKUP),)),
    ParameterDescriptor("payload", "object", argv=False),
)


class _Host(App[None]):
    def __init__(self, descriptors: tuple[ParameterDescriptor, ...] = DESCRIPTORS) -> None:
        super().__init__()
        self.descriptors = descriptors

    def compose(self) -> ComposeResult:
        yield ParameterFields(self.descriptors)


def _text(app: App[Any], selector: str) -> str:
    return str(app.query_one(selector, Static).content)


class TestTheFields:
    async def test_each_parameter_gets_the_field_its_declaration_reads_as(self) -> None:
        app = _Host()
        async with app.run_test():
            kinds = {
                name: type(app.query_one(f"#field-{name}")).__name__
                for name in ("title", "count", "urgent", "tags", "kind")
            }
            assert kinds == {
                "title": "Input",
                "count": "Input",
                "urgent": "Switch",
                "tags": "TextArea",
                "kind": "Select",
            }
            assert app.query_one("#field-count", Input).placeholder == "default 1"
            assert not app.query("#field-payload")
            shown = [str(static.content) for static in app.query(Static)]
            assert "Takes arguments this screen cannot send: payload." in shown

    async def test_a_help_line_and_a_choice_label_carrying_markup_show_as_typed(self) -> None:
        app = _Host()
        async with app.run_test():
            labels = [str(static.content) for static in app.query(Static)]
            assert "title  string  (required)\n" + MARKUP in labels
            select = app.query_one("#field-kind", Select)
            assert [str(prompt) for prompt, _ in select._options[1:]] == [MARKUP, "b"]

    async def test_no_unsendable_line_when_every_parameter_has_a_field(self) -> None:
        app = _Host(DESCRIPTORS[:1])
        async with app.run_test():
            shown = [str(static.content) for static in app.query(Static)]
            assert not [line for line in shown if line.startswith("Takes arguments")]


class TestTheValues:
    async def test_an_untouched_form_sends_nothing(self) -> None:
        app = _Host()
        async with app.run_test():
            assert app.query_one(ParameterFields).values() == {}

    async def test_each_filled_field_sends_its_flat_spelling(self) -> None:
        app = _Host()
        async with app.run_test() as pilot:
            app.query_one("#field-title", Input).value = "Hello"
            app.query_one("#field-count", Input).value = "3"
            app.query_one("#field-urgent", Switch).value = True
            app.query_one("#field-tags", TextArea).text = " red \n\nblue\n"
            app.query_one("#field-kind", Select).value = "b"
            await pilot.pause()
            assert app.query_one(ParameterFields).values() == {
                "title": "Hello",
                "count": "3",
                "urgent": "true",
                "tags": ["red", "blue"],
                "kind": "b",
            }

    async def test_a_switch_turned_back_off_sends_false(self) -> None:
        app = _Host()
        async with app.run_test() as pilot:
            switch = app.query_one("#field-urgent", Switch)
            switch.value = True
            await pilot.pause()
            switch.value = False
            await pilot.pause()
            assert app.query_one(ParameterFields).values() == {"urgent": "false"}


class TestTheRefusals:
    async def test_each_message_sits_below_its_field_and_the_rest_come_back(self) -> None:
        app = _Host()
        async with app.run_test():
            fields = app.query_one(ParameterFields)
            rest = fields.show_refusals(
                {
                    "non_field_errors": ["Check the form."],
                    "title": [MARKUP],
                    "tags": {1: ["Malformed."]},
                    "nope": ["Unknown."],
                }
            )
            assert rest == ["Check the form.", "nope: Unknown."]
            assert _text(app, "#refusal-title") == MARKUP
            assert _text(app, "#refusal-tags") == "1: Malformed."
            assert _text(app, "#refusal-count") == ""

    async def test_a_new_refusal_clears_the_last(self) -> None:
        app = _Host()
        async with app.run_test():
            fields = app.query_one(ParameterFields)
            fields.show_refusals({"title": ["Required."]})
            fields.show_refusals({})
            assert _text(app, "#refusal-title") == ""
