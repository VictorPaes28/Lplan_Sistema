import os
import sys

sys.path.insert(0, "/home/lplan/sistema_lplan")

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "Diario_obra.lplan_central.settings"
)

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()