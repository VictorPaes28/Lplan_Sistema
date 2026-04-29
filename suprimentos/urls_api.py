from django.urls import path
from . import views_analise_obra, views_api, views_controle
from painel_operacional import views as views_painel_operacional

app_name = 'suprimentos'

urlpatterns = [
    path('mapa-controle/summary', views_controle.mapa_controle_summary, name='mapa_controle_summary'),
    path('mapa-controle/items', views_controle.mapa_controle_items, name='mapa_controle_items'),
    path('item/<int:item_id>/detalhe/', views_api.item_detalhe, name='item_detalhe'),
    path('item/<int:item_id>/alocacoes/', views_api.item_alocacoes_json, name='item_alocacoes_json'),
    path('item/atualizar-campo/', views_api.item_atualizar_campo, name='item_atualizar_campo'),
    path('item/<int:item_id>/alocar/', views_api.item_alocar, name='item_alocar'),
    path('item/<int:item_id>/remover-alocacao/', views_api.item_remover_alocacao, name='item_remover_alocacao'),
    path('item/<int:item_id>/excluir/', views_api.item_excluir, name='item_excluir'),
    path('insumos/', views_api.listar_insumos, name='listar_insumos'),
    path('locais/', views_api.listar_locais, name='listar_locais'),
    path('recebimentos/<int:obra_id>/', views_api.recebimentos_obra, name='recebimentos_obra'),
    path('scs/', views_api.listar_scs_disponiveis, name='listar_scs'),
    path('busca-mobile/', views_api.busca_rapida_mobile, name='busca_mobile'),
    path('dashboard2/alocar/', views_api.dashboard2_alocar, name='dashboard2_alocar'),
    path('analise-obra/', views_analise_obra.analise_obra_api, name='analise_obra_api'),
    path('analise-obra/drilldown/', views_analise_obra.analise_obra_drilldown_api, name='analise_obra_drilldown_api'),
    path('ferramenta/ambientes/', views_painel_operacional.api_listar_ambientes, name='po_api_listar_ambientes'),
    path(
        'ferramenta/ambientes/<int:ambiente_id>/',
        views_painel_operacional.api_detalhe_ambiente,
        name='po_api_detalhe_ambiente',
    ),
    path(
        'ferramenta/ambientes/<int:ambiente_id>/elementos/',
        views_painel_operacional.api_listar_elementos,
        name='po_api_listar_elementos',
    ),
    path(
        'ferramenta/ambientes/<int:ambiente_id>/elementos/sync/',
        views_painel_operacional.api_sync_elementos,
        name='po_api_sync_elementos',
    ),
    path('ferramenta/ambientes/criar/', views_painel_operacional.api_criar_ambiente, name='po_api_criar_ambiente'),
    path(
        'ferramenta/ambientes/<int:ambiente_id>/adicionar-secao/',
        views_painel_operacional.api_adicionar_secao,
        name='po_api_adicionar_secao',
    ),
    path(
        'ferramenta/ambientes/<int:ambiente_id>/salvar-rascunho/',
        views_painel_operacional.api_salvar_rascunho,
        name='po_api_salvar_rascunho',
    ),
    path(
        'ferramenta/ambientes/<int:ambiente_id>/publicar/',
        views_painel_operacional.api_publicar_ambiente,
        name='po_api_publicar_ambiente',
    ),
]

