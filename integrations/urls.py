from django.urls import path

from .views import teams_bot_activity_view, trigger_powerbi_export_view

app_name = "integrations"

urlpatterns = [
    path("teams/bot/activity/", teams_bot_activity_view, name="teams_bot_activity"),
    path("powerbi/export/", trigger_powerbi_export_view, name="powerbi_export"),
]

