from django.urls import path
from . import views_api

app_name = 'suprimentos'

urlpatterns = [
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
]

