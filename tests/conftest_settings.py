from __future__ import annotations

import os
import tempfile

SECRET_KEY = "not-a-secret-this-is-the-test-suite"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django_spec_cli",
    "tests.commands_app",
    "tests.dispatch_app",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "TEST": {
            "NAME": os.path.join(
                tempfile.gettempdir(), f"django_spec_cli_tests_{os.getpid()}.sqlite3"
            ),
        },
    }
}

USE_TZ = True
