"""Fixtures the suite shares.

``keep_the_test_connection`` is the one: two modules call ``run_from_argv`` and
need it.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def keep_the_test_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    """For a test calling ``run_from_argv``, which closes every connection when it ends.

    That would close the one the test's transaction is on. Opt-in rather than
    autouse, so no other test runs with ``close_all`` patched out.
    """
    monkeypatch.setattr("django.db.connections.close_all", lambda: None)
