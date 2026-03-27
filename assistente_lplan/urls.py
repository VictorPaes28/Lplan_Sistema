from django.urls import path

from . import views

app_name = "assistente_lplan"

urlpatterns = [
    path("", views.assistant_home, name="home"),
    path("perguntar/", views.perguntar, name="perguntar"),
    path("feedback/", views.feedback, name="feedback"),
]

