"""
URL configuration for Sistema LPLAN Central - Unificado.

Estrutura de URLs:
  /               -> Core (Diário de Obra) - app principal
  /gestao/        -> Gestão de Aprovação (namespace: gestao)
  /mapa/          -> Mapa de Suprimentos (namespace: mapa_obras)
  /accounts/      -> Autenticação e Admin Central (namespace: accounts)
  /aprovacoes/    -> Central de Aprovações (workflow genérico)
  /engenharia/    -> Suprimentos/Engenharia (namespace: engenharia)
  /api/           -> APIs internas
  /admin/         -> Django Admin
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

from core.csrf_views import get_csrf_token

urlpatterns = [
    path('admin/', admin.site.urls),

    # === Core (Diário de Obra) - app principal no root ===
    path('', include('core.urls')),
    path('api/diario/', include('core.api_urls')),
    path('api/csrf-token/', get_csrf_token, name='api_csrf_token'),

    # === Gestão de Aprovação ===
    path('gestao/', include('gestao_aprovacao.urls')),
    # Tupla (urlconf, app_name) garante o namespace "impedimentos" para {% url 'impedimentos:...' %}
    path('impedimentos/', include(('impedimentos.urls', 'impedimentos'))),

    # === Mapa de Suprimentos ===
    path('mapa/', include('mapa_obras.urls')),

    # === Autenticação e Admin Central ===
    path('accounts/', include('accounts.urls')),

    # === Central de Aprovações (workflow genérico) ===
    path('aprovacoes/', include('workflow_aprovacao.urls')),

    # === Suprimentos / Engenharia ===
    path('engenharia/', include('suprimentos.urls_engenharia')),
    path('api/internal/', include('suprimentos.urls_api')),
    path('api/webhook/sienge/', include('suprimentos.urls_webhook')),
    path('assistente/', include('assistente_lplan.urls')),
    path('comunicados/', include('comunicados.urls')),
    # path('api/integrations/', include('integrations.urls')),  # Pausado — retomar quando ativar Teams/Azure

    # Redirect legado: /diario/xxx -> /xxx
    path('diario/', RedirectView.as_view(url='/', permanent=True)),
]

# /static/ → WhiteNoise (middleware). /media/ aqui porque o WhiteNoise não serve uploads.
# Em DEBUG: /media/ antes do path('', include('core.urls')) para o core não devolver 404 em ficheiros media.
if settings.DEBUG:
    urlpatterns = static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + urlpatterns
else:
    from django.views.static import serve

    urlpatterns = [
        path(settings.MEDIA_URL.strip('/') + '/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
    ] + urlpatterns

# 400 customizado: POST muito grande / muitos campos retornam JSON com código (ex.: UPLOAD_BODY_TOO_LARGE)
handler400 = 'core.error_handlers.bad_request'
