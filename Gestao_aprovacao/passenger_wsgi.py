"""
Passenger WSGI configuration for Django
Padrão cPanel/ServHost - configuração completa
"""

import os
import sys

# Caminho do projeto
project_home = '/home/lplan/public_html/gestao_aprovacao'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Configura o módulo de settings do Django
os.environ['DJANGO_SETTINGS_MODULE'] = 'gestao_aprovacao.settings'

# Carrega a aplicação WSGI do Django
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
