from django.urls import path

from . import views

app_name = 'recursos_humanos'

urlpatterns = [
    path('portal/<str:token>/', views.portal_candidato_view, name='portal'),
    path('portal/<str:token>/upload/<int:doc_pk>/', views.portal_upload_view, name='portal_upload'),
    path('portal/<str:token>/arquivo/<int:doc_pk>/', views.portal_arquivo_view, name='portal_arquivo'),
    path('portal/<str:token>/remover/<int:doc_pk>/', views.portal_remover_view, name='portal_remover'),
    path('', views.colaboradores_list_view, name='colaboradores'),
    path('colaboradores/', views.colaboradores_list_view, name='colaboradores_list'),
    path('colaboradores/<int:pk>/', views.colaborador_detalhe_view, name='colaborador_detalhe'),
    path('colaboradores/<int:pk>/json/', views.colaborador_json_view, name='colaborador_json'),
    path('colaboradores/<int:pk>/excluir/', views.colaborador_excluir_view, name='colaborador_excluir'),
    path('colaboradores/<int:pk>/desligar/', views.colaborador_desligar_view, name='colaborador_desligar'),
    path('colaboradores/<int:pk>/contrato/gerar/', views.contrato_gerar_view, name='contrato_gerar'),
    path('colaboradores/<int:pk>/contrato/upload/', views.contrato_upload_view, name='contrato_upload'),
    path('colaboradores/<int:pk>/contrato/download/', views.contrato_download_view, name='contrato_download'),
    path('colaboradores/<int:pk>/prazo-contrato/criar/', views.prazo_contrato_criar_view, name='prazo_contrato_criar'),
    path('prazo-contrato/<int:pk>/decisao/', views.prazo_contrato_decisao_view, name='prazo_contrato_decisao'),
    path('prazo-contrato/<int:pk>/decisao/json/', views.prazo_contrato_decisao_json_view, name='prazo_contrato_decisao_json'),
    path('prazo-contrato/<int:pk>/reativar/', views.prazo_contrato_reativar_view, name='prazo_contrato_reativar'),
    path('admissao/', views.admissao_view, name='admissao'),
    path('requisicao/<int:pk>/aprovar/', views.gestor_aprovar_requisicao_view, name='gestor_aprovar_requisicao'),
    path('admissao/nova/', views.admissao_nova_view, name='admissao_nova'),
    path('admissao/<int:pk>/atualizar/', views.admissao_atualizar_requisicao_view, name='admissao_atualizar_requisicao'),
    path('admissao/<int:pk>/acao/', views.admissao_acao_view, name='admissao_acao'),
    path('documento/<int:pk>/status/', views.documento_status_view, name='documento_status'),
    path('documento/<int:pk>/aprovar/', views.documento_aprovar_view, name='documento_aprovar'),
    path('documento/<int:pk>/rejeitar/', views.documento_rejeitar_view, name='documento_rejeitar'),
    path('documento/<int:pk>/upload/', views.documento_upload_view, name='documento_upload'),
    path('colaboradores/<int:pk>/documentos/<int:doc_pk>/solicitar-reenvio/', views.documento_solicitar_reenvio_view, name='documento_solicitar_reenvio'),
    path('alertas/', views.alertas_view, name='alertas'),
    path('alertas/configurar/', views.alertas_configurar_view, name='alertas_configurar'),
    path('alertas/whatsapp/', views.enviar_alertas_whatsapp_view, name='alertas_whatsapp'),
    path('documentos/', views.documentos_config_view, name='documentos_config'),
    path('cargos/', views.cargos_view, name='cargos'),
    path('cargos/catalogo/criar/', views.cargo_catalogo_create_view, name='cargo_catalogo_create'),
    path('cargos/rh/criar/', views.cargo_rh_quick_create_view, name='cargo_rh_quick_create'),
    path('cargos/<int:pk>/excluir/', views.cargo_excluir_view, name='cargo_excluir'),
]
