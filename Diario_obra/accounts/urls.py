from django.urls import path
from django.contrib.auth import views as auth_views
from . import views, views_admin

app_name = 'accounts'

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/', views.profile, name='profile'),
    path('home/', views.home, name='home'),
    
    # Admin Central (dashboard + gestão de obras do Mapa de Suprimentos)
    path('admin-central/', views_admin.admin_central, name='admin_central'),
    path('admin-central/analise-usuarios/', views_admin.analise_usuarios, name='admin_analise_usuarios'),
    path('admin-central/analise-usuarios/exportar-csv/', views_admin.analise_usuarios_export_csv, name='admin_analise_usuarios_export_csv'),
    path('admin-central/criar-obra/', views_admin.criar_obra, name='criar_obra'),
    path('admin-central/gerenciar-obras/', views_admin.gerenciar_obras, name='gerenciar_obras'),
    # Gestão de usuários: staff/superuser usam o Central (/central/usuarios/); demais usam /gestao/usuarios/ (gestao:list_users)
]
