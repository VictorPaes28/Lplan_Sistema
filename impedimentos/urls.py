from django.urls import path

from . import views

app_name = "impedimentos"

urlpatterns = [
    path("", views.home, name="home"),
    path("selecionar-obra/", views.select_obra, name="select_obra"),
    path("<int:obra_id>/mover-status/", views.update_status_ajax, name="update_status_ajax"),
    path(
        "<int:obra_id>/itens/<int:impedimento_id>/comentarios/",
        views.comentarios_impedimento_ajax,
        name="comentarios_impedimento_ajax",
    ),
    path(
        "<int:obra_id>/exportar-impeditivos-pdf/",
        views.export_impedimentos_pdf,
        name="export_impedimentos_pdf",
    ),
    path("<int:obra_id>/status/", views.list_status, name="list_status"),
    path(
        "<int:obra_id>/categorias/criar/",
        views.criar_categoria_ajax,
        name="criar_categoria_ajax",
    ),
    path(
        "<int:obra_id>/categorias/<int:categoria_id>/remover/",
        views.remover_categoria_ajax,
        name="remover_categoria_ajax",
    ),
    path(
        "<int:obra_id>/item/<int:impedimento_id>/",
        views.impedimento_detail_ajax,
        name="impedimento_detail_ajax",
    ),
    path(
        "<int:obra_id>/item/<int:impedimento_id>/update-field/",
        views.impedimento_update_field,
        name="impedimento_update_field",
    ),
    path(
        "<int:obra_id>/item/<int:impedimento_id>/arquivos/",
        views.impedimento_arquivo_upload,
        name="impedimento_arquivo_upload",
    ),
    path(
        "<int:obra_id>/item/<int:impedimento_id>/arquivos/<int:arquivo_id>/remover/",
        views.impedimento_arquivo_remover,
        name="impedimento_arquivo_remover",
    ),
    path(
        "<int:obra_id>/item/<int:impedimento_id>/atividades/",
        views.impedimento_atividades_ajax,
        name="impedimento_atividades_ajax",
    ),
    path(
        "<int:obra_id>/item/<int:impedimento_id>/subtarefas/",
        views.impedimento_subtarefas_ajax,
        name="impedimento_subtarefas_ajax",
    ),
    path("<int:obra_id>/", views.list_impedimentos, name="list_impedimentos"),
    path("itens/", views.legacy_list_impedimentos, name="legacy_list_impedimentos"),
    path("status/", views.legacy_list_status_redirect, name="legacy_list_status_redirect"),
]
