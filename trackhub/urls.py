from django.urls import path

from . import views

app_name = 'trackhub'

urlpatterns = [
    path('', views.fila_view, name='fila'),
    path('importados/', views.importados_view, name='importados'),
    path('criadas/', views.criadas_view, name='criadas'),
    path('por-obra/', views.por_obra_view, name='por_obra'),
    path('por-responsavel/', views.por_responsavel_view, name='por_responsavel'),
    path('calendario/', views.calendario_view, name='calendario'),
    path('pendencia/nova/', views.pendencia_criar_view, name='pendencia_criar'),
    path('tipo-custom/criar/', views.tipo_custom_criar_view, name='tipo_custom_criar'),
    path('pendencia/<int:pk>/json/', views.pendencia_detail_ajax, name='pendencia_detail_ajax'),
    path(
        'pendencia/<int:pk>/update-field/',
        views.pendencia_update_field,
        name='pendencia_update_field',
    ),
    path(
        'pendencia/<int:pk>/atividades/',
        views.pendencia_atividades_ajax,
        name='pendencia_atividades_ajax',
    ),
    path(
        'pendencia/<int:pk>/comentarios/',
        views.pendencia_comentarios_ajax,
        name='pendencia_comentarios_ajax',
    ),
    path(
        'pendencia/<int:pk>/etapa/adicionar/',
        views.etapa_adicionar_view,
        name='etapa_adicionar',
    ),
    path(
        'pendencia/<int:pk>/etapas/reordenar/',
        views.pendencia_etapas_reordenar_view,
        name='pendencia_etapas_reordenar',
    ),
    path('pendencia/<int:pk>/', views.pendencia_detalhe_view, name='pendencia_detalhe'),
    path('pendencia/<int:pk>/editar/', views.pendencia_editar_view, name='pendencia_editar'),
    path('pendencia/<int:pk>/concluir/', views.pendencia_concluir_view, name='pendencia_concluir'),
    path('pendencia/<int:pk>/cancelar/', views.pendencia_cancelar_view, name='pendencia_cancelar'),
    path('pendencia/<int:pk>/reativar/', views.pendencia_reativar_view, name='pendencia_reativar'),
    path('pendencia/<int:pk>/deletar/', views.pendencia_deletar_view, name='pendencia_deletar'),
    path('etapa/<int:pk>/concluir/', views.etapa_concluir_view, name='etapa_concluir'),
    path('etapa/<int:pk>/reabrir/', views.etapa_reabrir_view, name='etapa_reabrir'),
    path('etapa/<int:pk>/editar/', views.etapa_editar_view, name='etapa_editar'),
    path('etapa/<int:pk>/deletar/', views.etapa_deletar_view, name='etapa_deletar'),
    path('etapa/<int:pk>/notificar/', views.etapa_notificar_view, name='etapa_notificar'),
    path('pendencia/<int:pk>/comentar/', views.comentario_criar_view, name='comentario_criar'),
    path('pendencia/<int:pk>/anexo/upload/', views.anexo_upload_view, name='anexo_upload'),
    path('anexo/<int:pk>/deletar/', views.anexo_deletar_view, name='anexo_deletar'),
]
