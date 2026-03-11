"""
URL configuration for Sistema LPLAN Central - Unificado.

Estrutura de URLs:
  /               -> Core (Diário de Obra) - app principal
  /gestao/        -> Gestão de Aprovação (namespace: gestao)
  /mapa/          -> Mapa de Suprimentos (namespace: mapa_obras)
  /accounts/      -> Autenticação e Admin Central (namespace: accounts)
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

    # === Mapa de Suprimentos ===
    path('mapa/', include('mapa_obras.urls')),

    # === Autenticação e Admin Central ===
    path('accounts/', include('accounts.urls')),

    # === Suprimentos / Engenharia ===
    path('engenharia/', include('suprimentos.urls_engenharia')),
    path('api/internal/', include('suprimentos.urls_api')),
    path('api/webhook/sienge/', include('suprimentos.urls_webhook')),

    # Redirect legado: /diario/xxx -> /xxx
    path('diario/', RedirectView.as_view(url='/', permanent=True)),
]

# Em DEBUG: servir /static/ e /media/ ANTES do path('', include('core.urls'))
# senão o core engole /static/... e devolve 404 (CSS e imagens não carregam)
# Em produção: também servir /static/ a partir de STATIC_ROOT para o Mapa (supplymap.js etc.)
# rodar: python manage.py collectstatic --noinput
if settings.DEBUG:
    urlpatterns = static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + urlpatterns
    urlpatterns = static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) + urlpatterns
else:
    # Produção: servir estáticos e mídia (imagens/vídeos do diário) para evitar 404
    from django.views.static import serve
    urlpatterns = [
        path(settings.STATIC_URL.strip('/') + '/<path:path>', serve, {'document_root': settings.STATIC_ROOT}),
        path(settings.MEDIA_URL.strip('/') + '/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
    ] + urlpatterns
