import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from integrations.services import dispatch_event_on_commit
from integrations.teams_bot import process_teams_activity

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def teams_bot_activity_view(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "message": "Payload JSON inválido."}, status=400)

    result = process_teams_activity(payload)
    dispatch_event_on_commit(
        event_type="teams_bot_command_processed",
        source="teams_bot",
        actor_id=getattr(getattr(request, "user", None), "id", None),
        payload={
            "title": "Comando Teams processado",
            "details": result.message,
            "success": result.ok,
            "command": result.command_name,
        },
    )
    return JsonResponse(
        {
            "type": "message",
            "text": result.message,
            "ok": result.ok,
            "command": result.command_name,
            "data": result.payload or {},
        },
        status=200 if result.ok else 400,
    )


@require_POST
def trigger_powerbi_export_view(request):
    dispatch_event_on_commit(
        event_type="powerbi_export_incremental",
        payload={"title": "Exportação Power BI solicitada manualmente"},
        source="manual",
        actor_id=request.user.id if request.user.is_authenticated else None,
    )
    return JsonResponse({"ok": True, "message": "Exportação para Power BI enfileirada."})

