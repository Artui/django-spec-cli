from __future__ import annotations

import json
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder


def compact_json(value: Any) -> str:
    """``value`` as compact JSON, its text written as itself, as ``DjangoJSONEncoder`` encodes it."""
    return json.dumps(value, cls=DjangoJSONEncoder, ensure_ascii=False, separators=(",", ":"))
