from django.urls import path
from . import views_webhook

urlpatterns = [
    path('', views_webhook.webhook_sienge, name='sienge_webhook'),
]

