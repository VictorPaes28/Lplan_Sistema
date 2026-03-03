from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Diario_obra.core'

    def ready(self):
        import Diario_obra.core.signals