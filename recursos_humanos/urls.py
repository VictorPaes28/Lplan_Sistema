from django.urls import path

from . import views

app_name = 'recursos_humanos'

urlpatterns = [
    path('', views.colaboradores_list_view, name='colaboradores'),
    path('colaboradores/', views.colaboradores_list_view, name='colaboradores_list'),
    path('colaboradores/<int:pk>/', views.colaborador_detalhe_view, name='colaborador_detalhe'),
    path('admissao/', views.admissao_view, name='admissao'),
    path('admissao/nova/', views.admissao_nova_view, name='admissao_nova'),
    path('admissao/<int:pk>/acao/', views.admissao_acao_view, name='admissao_acao'),
    path('documento/<int:pk>/status/', views.documento_status_view, name='documento_status'),
    path('documento/<int:pk>/upload/', views.documento_upload_view, name='documento_upload'),
    path('alertas/', views.alertas_view, name='alertas'),
    path('documentos/', views.documentos_config_view, name='documentos_config'),
]
