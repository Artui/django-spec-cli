"""The row the suite's commands act on.

One row type owned by a user: enough for a selector to scope rows to its
principal, a retrieve to miss, a queryset to shape through ``select_related``,
and a write to change or be refused. The app has no migrations, so the test
database creates its table directly, as Django does for any unmigrated app.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Note(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notes"
    )
    title = models.CharField(max_length=100)
    archived = models.BooleanField(default=False)

    class Meta:
        app_label = "dispatch_app"
        ordering = ("pk",)
