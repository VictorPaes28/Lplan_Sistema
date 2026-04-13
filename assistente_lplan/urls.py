from django.urls import path

from . import views

app_name = "assistente_lplan"

urlpatterns = [
    path("", views.assistant_home, name="home"),
    path("definir-obra/", views.set_session_project, name="set_session_project"),
    path("perguntar/", views.perguntar, name="perguntar"),
    path("feedback/", views.feedback, name="feedback"),
    path("rdo-periodo-pdf/", views.download_rdo_period_pdf, name="rdo_period_pdf"),
]

