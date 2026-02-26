"""
Ponto de entrada WSGI para o Django (Lplan Central).
Use este arquivo como "Arquivo de inicialização" no painel Python para evitar
que o painel sobrescreva com um stub que causa recursão (imp.load_source).
"""
import os
import sys

# Limita threads do OpenBLAS/numpy em hospedagem compartilhada
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

# Raiz do repositório (sistema_lplan no servidor)
root = os.path.dirname(os.path.abspath(__file__))
project_home = os.path.join(root, 'Diario_obra')
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lplan_central.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
