"""
WSGI config for Diário de Obra V2.0 project.
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lplan_central.settings')

application = get_wsgi_application()

