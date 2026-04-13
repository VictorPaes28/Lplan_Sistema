"""
Service Worker e utilitários para modo offline do RDO.
"""
import os

from django.conf import settings
from django.http import HttpResponse


def rdo_offline_service_worker(request):
    """Serve o SW com escopo '/' (header Service-Worker-Allowed)."""
    path = os.path.join(settings.BASE_DIR, 'core', 'static', 'core', 'sw', 'rdo-offline-worker.js')
    with open(path, encoding='utf-8') as f:
        body = f.read()
    resp = HttpResponse(body, content_type='application/javascript; charset=utf-8')
    resp['Service-Worker-Allowed'] = '/'
    resp['Cache-Control'] = 'no-store, max-age=0'
    return resp
