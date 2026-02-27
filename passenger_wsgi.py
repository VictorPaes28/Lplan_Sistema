"""
Passenger WSGI na RAIZ de sistema_lplan (ao lado de Diario_obra).

Use este arquivo quando a "Raiz do aplicativo" no painel for sistema_lplan
(e não sistema_lplan/Diario_obra), para evitar o erro de relocação do virtualenv:
  shutil.Error: Cannot move a directory '.../virtualenv/sistema_lplan/' into itself
  '.../virtualenv/sistema_lplan/Diario_obra/'

Faz: (1) path para Diario_obra, (2) hook PyMySQL para cPanel, (3) carrega Django via lplan_central.wsgi.
NÃO REMOVER o bloco pymysql – no cPanel o mysqlclient não compila (falta Python.h).

ATENÇÃO: NUNCA use imp.load_source('wsgi', 'passenger_wsgi.py') aqui – isso carrega
este próprio arquivo de novo e causa RecursionError (loop infinito). O correto é
"from lplan_central.wsgi import application" no final.
"""
import os
import sys

# cPanel: limita threads do OpenBLAS/numpy (evita pthread_create failed em hospedagem compartilhada)
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'

# 1. Ajuste de caminho: aponta para a subpasta Diario_obra
project_root = os.path.dirname(os.path.abspath(__file__))
diario_obra_path = os.path.join(project_root, 'Diario_obra')
if diario_obra_path not in sys.path:
    sys.path.insert(0, diario_obra_path)

# 2. Truque do PyMySQL para o cPanel aceitar a conexão MySQL (não remover)
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass

# 3. Importação do WSGI do Django
from lplan_central.wsgi import application
