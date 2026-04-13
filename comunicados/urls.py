from django.urls import path

from . import painel, views

urlpatterns = [
    path('api/pendentes/', views.api_pendentes, name='api_comunicados_pendentes'),
    path('api/registrar/', views.api_registrar, name='api_comunicados_registrar'),
    # Painel do sistema (grupo Administrador)
    path('', painel.lista, name='comunicados_painel_lista'),
    path('criar/', painel.criar, name='comunicados_painel_criar'),
    path('editar/<int:pk>/', painel.editar, name='comunicados_painel_editar'),
    path('duplicar/<int:pk>/', painel.duplicar, name='comunicados_painel_duplicar'),
    path('toggle/<int:pk>/', painel.toggle, name='comunicados_painel_toggle'),
    path('encerrar/<int:pk>/', painel.encerrar, name='comunicados_painel_encerrar'),
    path('desempenho/<int:pk>/', painel.desempenho, name='comunicados_painel_desempenho'),
]
