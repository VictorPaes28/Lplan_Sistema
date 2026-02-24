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

urlpatterns = [
    path('admin/', admin.site.urls),

    # === Core (Diário de Obra) - app principal no root ===
    path('', include('core.urls')),
    path('api/diario/', include('core.api_urls')),

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

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
