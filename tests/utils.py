"""Helpers the suite's modules share: the repository root, and a fresh interpreter to probe in."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_python(source: str) -> subprocess.CompletedProcess[str]:
    """``source`` run by a fresh interpreter at the repository root, its output captured.

    For what this process cannot show once Django is set up in it: the check
    registry is process-wide, and the app registry is ready.
    """
    return subprocess.run(
        [sys.executable, "-c", source], cwd=REPO_ROOT, capture_output=True, text=True
    )


def run_project(installed: list[str], body: str) -> subprocess.CompletedProcess[str]:
    """``body`` run by a fresh interpreter whose settings list ``installed`` and an in-memory database."""
    return run_python(f"""
import django
from django.conf import settings
settings.configure(
    INSTALLED_APPS={installed!r},
    SECRET_KEY="probe",
    DATABASES={{"default": {{"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}}},
)
{body}
""")
