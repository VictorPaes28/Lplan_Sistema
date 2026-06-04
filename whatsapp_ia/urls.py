from django.urls import path

from whatsapp_ia import views_webhook

app_name = 'whatsapp_ia'

urlpatterns = [
    path('webhook/', views_webhook.webhook, name='webhook'),
]
