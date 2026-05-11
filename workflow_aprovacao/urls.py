from django.urls import path

from workflow_aprovacao import views

app_name = 'workflow_aprovacao'

urlpatterns = [
    path('', views.home, name='home'),
    path('painel/', views.dashboard, name='dashboard'),
    path('sincronizar/forcar/', views.force_sync, name='force_sync'),
    path('config/integracoes/', views.outbox_list, name='outbox_list'),
    path('config/integracoes/<int:pk>/enviar/', views.outbox_dispatch, name='outbox_dispatch'),
    path('fila/', views.pending_list, name='pending'),
    path('processo/<int:pk>/', views.process_detail, name='process_detail'),
    path(
        'processo/<int:pk>/assinatura/comprovante.pdf',
        views.process_signature_receipt_pdf,
        name='process_signature_receipt_pdf',
    ),
    path(
        'processo/<int:pk>/sienge/anexo/',
        views.sienge_process_attachment_download,
        name='sienge_process_attachment',
    ),
    path('config/fluxos/', views.config_flow_list, name='config_flow_list'),
    path('config/fluxos/<int:pk>/', views.flow_edit, name='flow_edit'),
    path('config/pendencias/', views.config_backlog_list, name='config_backlog_list'),
    path(
        'config/pendencias/<int:pk>/dispensar/',
        views.config_backlog_dismiss,
        name='config_backlog_dismiss',
    ),
    path(
        'config/pendencias/<int:pk>/reabrir/',
        views.config_backlog_reopen,
        name='config_backlog_reopen',
    ),
    path(
        'config/pendencias/<int:pk>/tentar-criar/',
        views.config_backlog_retry,
        name='config_backlog_retry',
    ),
]
