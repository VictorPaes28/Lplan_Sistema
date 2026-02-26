"""
Passenger WSGI na RAIZ de sistema_lplan (ao lado de Diario_obra).

Use este arquivo quando a "Raiz do aplicativo" no painel for sistema_lplan
(e não sistema_lplan/Diario_obra), para evitar o erro de relocação do virtualenv:
  shutil.Error: Cannot move a directory '.../virtualenv/sistema_lplan/' into itself
  '.../virtualenv/sistema_lplan/Diario_obra/'

Este script adiciona Diario_obra ao path e carrega o Django a partir de lá.
"""
import os
import sys

# Raiz do repositório (sistema_lplan no servidor)
root = os.path.dirname(os.path.abspath(__file__))
# Pasta onde está manage.py e lplan_central
project_home = os.path.join(root, 'Diario_obra')
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lplan_central.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
