"""
URLs específicas para a API REST (DRF).
Separado do frontend para evitar conflitos de rotas.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProjectViewSet,
    ActivityViewSet,
    ConstructionDiaryViewSet,
    DiaryImageViewSet,
    DailyWorkLogViewSet,
    LaborViewSet,
    EquipmentViewSet,
)

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'activities', ActivityViewSet, basename='activity')
router.register(r'diaries', ConstructionDiaryViewSet, basename='diary')
router.register(r'diary-images', DiaryImageViewSet, basename='diary-image')
router.register(r'work-logs', DailyWorkLogViewSet, basename='work-log')
router.register(r'labor', LaborViewSet, basename='labor')
router.register(r'equipment', EquipmentViewSet, basename='equipment')

urlpatterns = [
    path('', include(router.urls)),
]

