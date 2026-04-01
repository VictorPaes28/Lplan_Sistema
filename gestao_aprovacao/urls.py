from django.urls import path
from . import views

app_name = 'gestao'

urlpatterns = [
    path('', views.home, name='home'),
    # Usuários: staff é redirecionado ao central; responsável por empresa usa as views aqui
    path('usuarios/', views.list_users_or_redirect_central, name='list_users'),
    path('usuarios/criar/', views.create_user_or_redirect_central, name='create_user'),
    path('usuarios/<int:pk>/editar/', views.edit_user_or_redirect_central, name='edit_user'),
    path('usuarios/<int:pk>/excluir/', views.delete_user_or_redirect_central, name='delete_user'),
    
    # CRUD WorkOrder
    path('pedidos/', views.list_workorders, name='list_workorders'),
    path('pedidos/criar/', views.create_workorder, name='create_workorder'),
    path('pedidos/<int:pk>/', views.detail_workorder, name='detail_workorder'),
    path('pedidos/<int:pk>/editar/', views.edit_workorder, name='edit_workorder'),
    
    # Aprovação
    path('pedidos/<int:pk>/aprovar/', views.approve_workorder, name='approve_workorder'),
    path('pedidos/<int:pk>/reprovar/', views.reject_workorder, name='reject_workorder'),
    
    # Anexos
    path('pedidos/<int:pk>/anexos/upload/', views.upload_attachment, name='upload_attachment'),
    path('anexos/<int:pk>/deletar/', views.delete_attachment, name='delete_attachment'),
    
    # CRUD Empresa
    path('empresas/', views.list_empresas, name='list_empresas'),
    path('empresas/criar/', views.create_empresa, name='create_empresa'),
    path('empresas/<int:pk>/', views.detail_empresa, name='detail_empresa'),
    path('empresas/<int:pk>/editar/', views.edit_empresa, name='edit_empresa'),
    
    # CRUD Obra
    path('obras/', views.list_obras, name='list_obras'),
    path('obras/criar/', views.create_obra, name='create_obra'),
    path('obras/<int:pk>/', views.detail_obra, name='detail_obra'),
    path('obras/<int:pk>/editar/', views.edit_obra, name='edit_obra'),
    path('obras/<int:pk>/permissoes/', views.manage_obra_permissions, name='manage_obra_permissions'),
    
    # Gerenciamento de Usuários
    path('usuarios/', views.list_users, name='list_users'),
    path('usuarios/criar/', views.create_user, name='create_user'),
    path('usuarios/<int:pk>/editar/', views.edit_user, name='edit_user'),
    path('usuarios/<int:pk>/excluir/', views.delete_user, name='delete_user'),
    
    # Perfil do Usuário
    path('meu-perfil/', views.edit_my_profile, name='edit_my_profile'),
    
    # Notificações
    path('notificacoes/', views.list_notificacoes, name='list_notificacoes'),
    path('notificacoes/<int:pk>/marcar-lida/', views.marcar_notificacao_lida, name='marcar_notificacao_lida'),
    path('api/notificacoes/count/', views.get_notificacoes_count, name='get_notificacoes_count'),
    
    # Exclusão de pedidos
    path('pedidos/<int:pk>/solicitar-exclusao/', views.solicitar_exclusao, name='solicitar_exclusao'),
    path('pedidos/<int:pk>/aprovar-exclusao/', views.aprovar_exclusao, name='aprovar_exclusao'),
    path('pedidos/<int:pk>/rejeitar-exclusao/', views.rejeitar_exclusao, name='rejeitar_exclusao'),
    path('pedidos/<int:pk>/comentar/', views.add_comment, name='add_comment'),
    
    # API de desempenho (apenas admin)
    path('desempenho-equipe/', views.desempenho_equipe, name='desempenho_equipe'),
    path('api/desempenho-equipe/', views.desempenho_equipe_api, name='desempenho_equipe_api'),
    path('api/desempenho-solicitantes/', views.desempenho_solicitantes_api, name='desempenho_solicitantes_api'),
    path('exportar-historico-solicitante/<int:solicitante_id>/', views.exportar_historico_solicitante, name='exportar_historico_solicitante'),
    
    # Servir arquivos media em produção
    path('media/<path:path>', views.serve_media_file, name='serve_media_file'),
    
    # Logs de Email (apenas admin)
    path('emails/logs/', views.list_email_logs, name='list_email_logs'),
    path('emails/logs/<int:log_id>/reenviar/', views.reenviar_email, name='reenviar_email'),
    
    # Marcar pedido como analisado (apenas para os Luizes)
    path('pedidos/<int:pk>/marcar-analisado/', views.marcar_pedido_analisado, name='marcar_pedido_analisado'),
]
