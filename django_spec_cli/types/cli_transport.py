from __future__ import annotations

from typing import Final

CLI_TRANSPORT: Final = "cli"
"""What a ``SpecCommand`` stamps under the kernel's ``TRANSPORT_KEY``: the plain string ``"cli"``.

A callable reads it with the kernel's ``call_transport``, or compares
``call_context["transport"] == "cli"`` with nothing imported. This package owns
the string and the kernel lists no transports; it is a public contract, so it
never changes."""
