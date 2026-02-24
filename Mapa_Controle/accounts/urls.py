from django.urls import path
from django.contrib.auth import views as auth_views
from . import views, views_admin

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/', views.profile, name='profile'),
    path('home/', views.home, name='home'),
    
    # Admin Central
    path('admin-central/', views_admin.admin_central, name='admin_central'),
    path('admin-central/criar-usuario/', views_admin.criar_usuario, name='criar_usuario'),
    path('admin-central/gerenciar-usuarios/', views_admin.gerenciar_usuarios, name='gerenciar_usuarios'),
    path('admin-central/editar-usuario/<int:user_id>/', views_admin.editar_usuario, name='editar_usuario'),
    path('admin-central/criar-obra/', views_admin.criar_obra, name='criar_obra'),
    path('admin-central/gerenciar-obras/', views_admin.gerenciar_obras, name='gerenciar_obras'),
]
