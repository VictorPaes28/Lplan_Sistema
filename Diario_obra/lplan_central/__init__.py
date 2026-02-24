# LPLAN Sistema Central - Unificado

# Importa Celery app para garantir que seja carregado quando Django iniciar
# Importação opcional - permite que o sistema funcione sem Celery instalado
try:
    from .celery import app as celery_app
    __all__ = ('celery_app',)
except ImportError:
    # Celery não está instalado - sistema funciona sem processamento assíncrono
    celery_app = None
    __all__ = ()
