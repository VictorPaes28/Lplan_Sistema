"""
URL configuration for Diário de Obra V2.0 project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # Frontend routes (login, dashboard, etc.) - vem primeiro
    path('', include('core.urls')),
    # API REST - separado para evitar conflitos
    path('api/', include('core.api_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

