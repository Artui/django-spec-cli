"""A command module that fails to import, as a third-party command missing a dependency does."""

from __future__ import annotations

raise RuntimeError("this command module cannot be imported")
