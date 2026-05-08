from django.apps import AppConfig


class TrackhubConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'trackhub'

    def ready(self):
        import trackhub.signals  # noqa: F401
