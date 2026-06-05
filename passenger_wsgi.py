import os
import sys

# Mitigação para ambientes cPanel/Passenger com limites de processos/threads.
# Evita estouro de threads de OpenBLAS/NumPy durante import de pandas/numpy.
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')
os.environ.setdefault('NUMEXPR_NUM_THREADS', '1')

# Raiz do projeto (onde estão manage.py e lplan_central)
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)  # cPanel: Passenger pode rodar com cwd errado; .env e paths relativos passam a funcionar

# cPanel: PyMySQL como substituto de mysqlclient (obrigatório se não tiver mysqlclient)
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass

# Garantir que o .env seja encontrado (Passenger pode rodar com cwd diferente)
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lplan_central.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()