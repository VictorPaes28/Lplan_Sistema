from django.urls import path

from . import views

app_name = 'mapa_geo'

urlpatterns = [
    path('selecionar-obra/', views.selecionar_obra_view, name='selecionar_obra'),
    path('', views.mapa_view, name='mapa'),
    path('importar/', views.importar_view, name='importar'),
    path('exportar/', views.exportar_view, name='exportar'),
    path('api/features/', views.api_features_view, name='api_features'),
    path('api/features/<int:pk>/', views.api_feature_detail_view, name='api_feature_detail'),
    path('api/activities/', views.api_activities_view, name='api_activities'),
    path('api/timeline/', views.api_timeline_view, name='api_timeline'),
    path('api/summary/', views.api_summary_view, name='api_summary'),
    path('api/sync/', views.api_sync_view, name='api_sync'),
    path('api/folders/', views.api_folders_view, name='api_folders'),
    path('api/alerts/', views.api_alerts_view, name='api_alerts'),
    path('api/compare/', views.api_compare_view, name='api_compare'),
    path('relatorio/', views.relatorio_view, name='relatorio'),
    path('panorama/', views.panorama_view, name='panorama'),
]
