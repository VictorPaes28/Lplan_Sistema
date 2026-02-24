"""
URL configuration for supplymap project.
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('obras/', include('obras.urls')),  # URLs de seleção de obra
    path('engenharia/', include('suprimentos.urls_engenharia')),
    path('api/internal/', include('suprimentos.urls_api')),
    path('api/webhook/sienge/', include('suprimentos.urls_webhook')),
    path('', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login_redirect'),
]

