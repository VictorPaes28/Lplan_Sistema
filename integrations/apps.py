from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "integrations"
    verbose_name = "Integracoes"

    def ready(self):
        pass  # Pausado — descomentar quando ativar Teams/Azure
        # from . import signals  # noqa: F401

