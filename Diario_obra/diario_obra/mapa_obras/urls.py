from django.urls import path
from . import views

app_name = 'obras'

urlpatterns = [
    path('selecionar/<int:obra_id>/', views.selecionar_obra, name='selecionar'),
    path('api/locais/<int:obra_id>/', views.api_locais_por_obra, name='api_locais'),
]

