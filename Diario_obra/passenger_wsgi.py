"""
Passenger WSGI para cPanel – Diário de Obra (Lplan Central).
O cPanel usa este arquivo como ponto de entrada da aplicação.
Ajuste project_home se o caminho no servidor for diferente.
"""
import os
import sys

# Pasta onde está manage.py (Diario_obra)
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lplan_central.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
