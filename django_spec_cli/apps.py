"""The app a project lists to have its open specs reported by ``manage.py check``."""

from __future__ import annotations

from django.apps import AppConfig
from django.core.checks import register

from django_service_specs.checks import check_unguarded_specs


class DjangoServiceSpecsConfig(AppConfig):
    """Registers the unguarded-spec system check, and does nothing else.

    Optional: the package works unlisted, and a project that does not list it
    gets no check and no sign that it is missing. It owns no models, so it
    sets no ``default_auto_field``.

    The check carries no tag, and in particular not ``Tags.security``: a
    ``SpecCommand`` is a mistake-prevention and attribution surface, not an
    authorization boundary, and a security tag would say it is one.

    The import of the check is at the top of this module, which Django
    imports before the app registry is ready. That holds because nothing the
    package imports reaches a model or ``get_user_model`` at import time
    (test_importing_the_app_before_setup_loads_no_model).
    """

    name = "django_service_specs"

    def ready(self) -> None:
        register(check_unguarded_specs)
