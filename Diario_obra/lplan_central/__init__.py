# LPLAN Sistema Central - Unificado

# MySQL no cPanel: usar PyMySQL (mysqlclient exige compilação e Python.h)
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass

# Importa Celery app para garantir que seja carregado quando Django iniciar
try:
    from .celery import app as celery_app
    __all__ = ('celery_app',)
except ImportError:
    celery_app = None
    __all__ = ()
