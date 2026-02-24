from django.urls import path
from django.http import Http404
from . import views_engenharia

app_name = 'engenharia'

def dashboard_removed(request):
    """View para retornar 404 se alguém tentar acessar o dashboard antigo."""
    raise Http404("Dashboard removido. Use /engenharia/dashboard-2/")

urlpatterns = [
    path('mapa/', views_engenharia.mapa_engenharia, name='mapa'),
    path('mapa/exportar-excel/', views_engenharia.exportar_mapa_excel, name='exportar_excel'),
    path('mapa/criar-item/', views_engenharia.criar_item_mapa, name='criar_item'),
    path('mapa/novo-levantamento/', views_engenharia.criar_levantamento_rapido, name='novo_levantamento'),
    path('mapa/importar-sienge/', views_engenharia.importar_sienge_upload, name='importar_sienge'),
    path('insumo/criar/', views_engenharia.criar_insumo, name='criar_insumo'),
    # Dashboard antigo removido - retorna 404
    path('dashboard/', dashboard_removed, name='dashboard'),
    path('dashboard-2/', views_engenharia.dashboard_2, name='dashboard_2'),
]

