"""Helpers the render modules share: one encoding of a value as JSON, for a line and for a cell."""

from __future__ import annotations

import json
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder


def compact_json(value: Any) -> str:
    """``value`` as compact JSON, its text written as itself, as ``DjangoJSONEncoder`` encodes it.

    What the encoder has no spelling for raises ``TypeError``.
    """
    return json.dumps(value, cls=DjangoJSONEncoder, ensure_ascii=False, separators=(",", ":"))
