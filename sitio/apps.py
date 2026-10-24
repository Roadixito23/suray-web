from django.apps import AppConfig


class SitioConfig(AppConfig):
    name = 'sitio'

    def ready(self):
        from . import signals  # noqa: F401
