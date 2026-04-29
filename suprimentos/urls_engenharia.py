from django.urls import path
from django.views.generic import RedirectView
from . import views_analise_obra, views_engenharia, views_controle, views_mapa_servico
from painel_operacional import views as views_painel_operacional

app_name = 'engenharia'

urlpatterns = [
    path('mapa/', views_engenharia.mapa_engenharia, name='mapa'),
    path('mapa-servico/', views_mapa_servico.mapa_servico, name='mapa_servico'),
    path('mapa-controle/', views_controle.mapa_controle, name='mapa_controle'),
    path('mapa-controle/importar/', views_controle.importar_mapa_controle, name='importar_mapa_controle'),
    path('mapa/exportar-excel/', views_engenharia.exportar_mapa_excel, name='exportar_excel'),
    path('mapa/criar-item/', views_engenharia.criar_item_mapa, name='criar_item'),
    path('mapa/novo-levantamento/', views_engenharia.criar_levantamento_rapido, name='novo_levantamento'),
    path('mapa/importar-sienge/', views_engenharia.importar_sienge_upload, name='importar_sienge'),
    path('mapa/importar-sienge/excluir/<int:pk>/', views_engenharia.excluir_importacao_sienge, name='excluir_importacao_sienge'),
    path('insumo/criar/', views_engenharia.criar_insumo, name='criar_insumo'),
    # Dashboard antigo redireciona para o novo
    path('dashboard/', RedirectView.as_view(pattern_name='engenharia:dashboard_2', permanent=True), name='dashboard_redirect'),
    path('dashboard-2/', views_engenharia.dashboard_2, name='dashboard_2'),
    path('analise-obra/', views_analise_obra.analise_obra, name='analise_obra'),
    path('ferramenta/', views_painel_operacional.ferramenta_shell, name='ferramenta_shell'),
    path(
        'ferramenta/ambientes/<int:ambiente_id>/',
        views_painel_operacional.editor_ambiente,
        name='ferramenta_editor_ambiente',
    ),
]

