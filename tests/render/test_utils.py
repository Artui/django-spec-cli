from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from django_spec_cli.render.utils import compact_json


def test_compact_json_has_no_spaces_and_writes_text_as_itself() -> None:
    assert compact_json({"city": "Zürich", "ids": [1, 2]}) == '{"city":"Zürich","ids":[1,2]}'


def test_compact_json_encodes_what_django_s_encoder_does() -> None:
    assert compact_json([Decimal("12.50"), dt.date(2024, 6, 1)]) == '["12.50","2024-06-01"]'


def test_compact_json_refuses_what_it_cannot_encode() -> None:
    with pytest.raises(TypeError):
        compact_json(object())
