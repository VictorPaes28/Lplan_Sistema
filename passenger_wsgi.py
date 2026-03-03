import os
import sys

# Raiz do projeto (onde estão manage.py e lplan_central)
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lplan_central.settings")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()