from __future__ import annotations

from django.db import models


class Status(models.TextChoices):
    """A choices enum, whose label a table cell shows in place of its stored value."""

    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
