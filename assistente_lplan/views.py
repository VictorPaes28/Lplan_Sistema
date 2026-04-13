from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, timedelta

from django.conf import settings
from django.core import signing
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from assistente_lplan.models import AssistantQuestionLog, AssistantResponseLog
from assistente_lplan.services.diario_service import DiarioAssistantService
from assistente_lplan.services.orchestrator import AssistantOrchestrator
from assistente_lplan.services.permissions import AssistantPermissionService
from assistente_lplan.services.learning import GuidedLearningService
from assistente_lplan.services.messages import MessageCatalog
from assistente_lplan.services.suggested_questions import build_assistant_home_context
from core.models import Project
from core.utils.rdo_period_pdf import generate_rdo_period_pdf_bytes

logger = logging.getLogger(__name__)


def _resolve_history_limit(setting_name: str, default: int) -> int:
    raw_value = getattr(settings, setting_name, default)
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        value = default
    return max(1, value)


SESSION_HISTORY_KEY = "assistente_lplan_history"
DEFAULT_HISTORY_ITEMS = 5
MAX_SESSION_HISTORY_ITEMS = _resolve_history_limit("ASSISTENTE_LPLAN_SESSION_HISTORY_ITEMS", DEFAULT_HISTORY_ITEMS)
MAX_UI_HISTORY_ITEMS = _resolve_history_limit("ASSISTENTE_LPLAN_UI_HISTORY_ITEMS", DEFAULT_HISTORY_ITEMS)
MAX_LOGS_PER_USER = getattr(settings, "ASSISTENTE_LPLAN_MAX_LOGS_PER_USER", 3000)
LOG_RETENTION_DAYS = getattr(settings, "ASSISTENTE_LPLAN_LOG_RETENTION_DAYS", 180)
CLEANUP_USER_INTERVAL_SECONDS = getattr(settings, "ASSISTENTE_LPLAN_CLEANUP_INTERVAL_SECONDS", 3600)
CACHE_TTL_SECONDS = 1000


@login_required
def assistant_home(request):
    history = _load_persistent_history(request.user, limit=MAX_UI_HISTORY_ITEMS)
    assistant_ctx = build_assistant_home_context(request)
    if assistant_ctx.get("persist_session_project") and assistant_ctx.get("selected_project_id"):
        try:
            p = Project.objects.get(pk=int(assistant_ctx["selected_project_id"]), is_active=True)
        except (Project.DoesNotExist, TypeError, ValueError):
            pass
        else:
            request.session["selected_project_id"] = p.id
            request.session["selected_project_name"] = p.name
            request.session["selected_project_code"] = p.code
            request.session.modified = True

    return render(
        request,
        "assistente_lplan/home.html",
        {
            "history": history,
            "suggested_questions": assistant_ctx["suggested_questions"],
            "suggestion_groups": assistant_ctx["suggestion_groups"],
            "suggestion_groups_primary": assistant_ctx.get("suggestion_groups_primary") or [],
            "suggestion_groups_more": assistant_ctx.get("suggestion_groups_more") or [],
            "active_project": assistant_ctx["active_project"],
            "welcome_lines": assistant_ctx["welcome_lines"],
            "selected_project_id": assistant_ctx["selected_project_id"],
            "available_projects": assistant_ctx.get("available_projects") or [],
            "history_limit": MAX_UI_HISTORY_ITEMS,
        },
    )


@login_required
@require_http_methods(["POST"])
def set_session_project(request):
    """Define a obra na sessão a partir do assistente (acesso validado)."""
    pid_raw = (request.POST.get("project_id") or "").strip()
    try:
        pid = int(pid_raw)
    except (TypeError, ValueError):
        return redirect("assistente_lplan:home")

    perm = AssistantPermissionService(request.user)
    scope = perm.build_scope()
    qs = Project.objects.filter(is_active=True, id=pid)
    if scope.role != "admin":
        qs = qs.filter(id__in=scope.project_ids)
    project = qs.first()
    if not project:
        return redirect("assistente_lplan:home")

    request.session["selected_project_id"] = project.id
    request.session["selected_project_name"] = project.name
    request.session["selected_project_code"] = project.code
    request.session.modified = True
    return redirect("assistente_lplan:home")


@login_required
@require_http_methods(["POST"])
def perguntar(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        msg = MessageCatalog.resolve("assistant.api.invalid_json", {"path": request.path, "status": 400})
        return JsonResponse({"error": msg["text"], "message_code": msg["code"], "next_steps": msg["next_steps"]}, status=400)

    question = (payload.get("pergunta") or "").strip()
    context = payload.get("contexto") or {}
    if not isinstance(context, dict):
        context = {}
    if request.session.get("selected_project_id") and "selected_project_id" not in context:
        context["selected_project_id"] = request.session.get("selected_project_id")
    if not question:
        msg = MessageCatalog.resolve("assistant.api.question_required", {"path": request.path, "status": 400})
        return JsonResponse({"error": msg["text"], "message_code": msg["code"], "next_steps": msg["next_steps"]}, status=400)

    qlog = AssistantQuestionLog.objects.create(
        user=request.user,
        question=question,
        context=context,
    )

    cache_key = _build_question_cache_key(request.user.id, question, context)
    cached_payload = cache.get(cache_key)
    if cached_payload:
        normalized = _normalize_response_payload(cached_payload)
        qlog.intent = str((normalized.get("raw_data") or {}).get("intent", ""))
        qlog.entities = (normalized.get("raw_data") or {}).get("entities", {})
        qlog.domain = str((normalized.get("raw_data") or {}).get("domain", ""))
        qlog.used_llm = bool((normalized.get("raw_data") or {}).get("used_llm", False))
        qlog.success = True
        qlog.save(update_fields=["intent", "entities", "domain", "used_llm", "success"])
        AssistantResponseLog.objects.create(
            question_log=qlog,
            summary=normalized.get("summary", "")[:400],
            response_payload=normalized,
        )
        _append_session_history(request, question, normalized)
        _schedule_user_history_cleanup(request.user.id)
        normalized["question_log_id"] = qlog.id
        normalized.setdefault("raw_data", {})
        normalized["raw_data"]["question_log_id"] = qlog.id
        return JsonResponse(normalized, status=200)

    try:
        response, meta = AssistantOrchestrator(user=request.user).handle(question=question, context=context)
        payload_out = _normalize_response_payload(response.to_dict())

        qlog.intent = str(meta.get("intent", ""))
        qlog.entities = meta.get("entities", {})
        qlog.domain = str(meta.get("domain", ""))
        qlog.used_llm = bool(meta.get("used_llm", False))
        qlog.success = True
        qlog.save(update_fields=["intent", "entities", "domain", "used_llm", "success"])

        AssistantResponseLog.objects.create(
            question_log=qlog,
            summary=payload_out.get("summary", "")[:400],
            response_payload=payload_out,
        )
        _append_session_history(request, question, payload_out)
        _schedule_user_history_cleanup(request.user.id)
        payload_out["question_log_id"] = qlog.id
        payload_out.setdefault("raw_data", {})
        payload_out["raw_data"]["question_log_id"] = qlog.id
        cache.set(cache_key, payload_out, CACHE_TTL_SECONDS)
        return JsonResponse(payload_out, status=200)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Falha ao processar pergunta do assistente.")
        qlog.success = False
        qlog.error_message = str(exc)[:1000]
        qlog.save(update_fields=["success", "error_message"])
        msg = MessageCatalog.resolve(
            "assistant.api.processing_failed",
            {"path": request.path, "status": 500, "question": question, "role": getattr(request.user, "username", "")},
        )
        fallback_payload = _normalize_response_payload(
            {
                "summary": msg["text"],
                "alerts": [{"level": "error", "message": msg["text"]}],
                "badges": ["Erro"],
                "raw_data": {"message_code": msg["code"], "message_kind": msg["kind"], "next_steps": msg["next_steps"]},
            }
        )
        AssistantResponseLog.objects.create(
            question_log=qlog,
            summary=msg["text"][:400],
            response_payload=fallback_payload,
        )
        _schedule_user_history_cleanup(request.user.id)
        return JsonResponse(fallback_payload, status=500)


@login_required
@require_http_methods(["GET"])
def download_rdo_period_pdf(request):
    """Download do PDF consolidado de RDO (token assinado gerado pelo assistente)."""
    token = (request.GET.get("t") or "").strip()
    if not token:
        raise Http404()

    try:
        data = signing.loads(token, salt=DiarioAssistantService.RDO_PERIOD_SIGN_SALT, max_age=86400 * 7)
    except signing.BadSignature:
        raise Http404() from None

    if int(data.get("u", 0)) != int(request.user.id):
        return HttpResponseForbidden("Link invalido para este usuario.")

    try:
        pid = int(data["p"])
        d0 = date.fromisoformat(data["d0"])
        d1 = date.fromisoformat(data["d1"])
    except (KeyError, TypeError, ValueError):
        raise Http404() from None

    perm = AssistantPermissionService(request.user)
    scope = perm.build_scope()
    qs = Project.objects.filter(is_active=True, id=pid)
    if scope.role != "admin":
        qs = qs.filter(id__in=scope.project_ids)
    project = qs.first()
    if not project:
        raise Http404()

    buf = generate_rdo_period_pdf_bytes(project, d0, d1)
    if not buf:
        raise Http404()

    code = (project.code or "obra").replace(" ", "_")
    fname = f"RDO_consolidado_{code}_{d0}_{d1}.pdf"
    return FileResponse(buf, content_type="application/pdf", as_attachment=True, filename=fname)


@login_required
@require_http_methods(["POST"])
def feedback(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        msg = MessageCatalog.resolve("assistant.api.invalid_json", {"path": request.path, "status": 400})
        return JsonResponse({"error": msg["text"], "message_code": msg["code"], "next_steps": msg["next_steps"]}, status=400)

    question_log_id = payload.get("question_log_id")
    helpful = payload.get("helpful")
    corrected_intent = (payload.get("corrected_intent") or "").strip()
    corrected_entities = payload.get("corrected_entities") or {}
    note = (payload.get("note") or "").strip()

    if not question_log_id:
        msg = MessageCatalog.resolve("assistant.api.feedback_question_log_required", {"path": request.path, "status": 400})
        return JsonResponse({"error": msg["text"], "message_code": msg["code"]}, status=400)
    if helpful is None:
        msg = MessageCatalog.resolve("assistant.api.feedback_helpful_required", {"path": request.path, "status": 400})
        return JsonResponse({"error": msg["text"], "message_code": msg["code"]}, status=400)
    if not isinstance(corrected_entities, dict):
        msg = MessageCatalog.resolve("assistant.api.feedback_entities_type", {"path": request.path, "status": 400})
        return JsonResponse({"error": msg["text"], "message_code": msg["code"]}, status=400)

    try:
        feedback_obj = GuidedLearningService.register_feedback(
            user=request.user,
            question_log_id=int(question_log_id),
            helpful=bool(helpful),
            corrected_intent=corrected_intent,
            corrected_entities=corrected_entities,
            note=note,
        )
    except AssistantQuestionLog.DoesNotExist:
        msg = MessageCatalog.resolve("assistant.api.feedback_not_found", {"path": request.path, "status": 404})
        return JsonResponse({"error": msg["text"], "message_code": msg["code"]}, status=404)
    except PermissionError:
        msg = MessageCatalog.resolve("assistant.api.feedback_forbidden", {"path": request.path, "status": 403})
        return JsonResponse({"error": msg["text"], "message_code": msg["code"]}, status=403)
    except ValueError:
        msg = MessageCatalog.resolve("assistant.api.feedback_invalid_id", {"path": request.path, "status": 400})
        return JsonResponse({"error": msg["text"], "message_code": msg["code"]}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "feedback_id": feedback_obj.id,
            "status": feedback_obj.status,
            "message": "Feedback registrado. Regras sugeridas ficam pendentes de aprovacao.",
        },
        status=200,
    )


def _append_session_history(request, question: str, response_payload: dict) -> None:
    history = request.session.get(SESSION_HISTORY_KEY, [])
    history.append(
        {
            "question": question,
            "summary": response_payload.get("summary", ""),
            "badges": response_payload.get("badges", []),
        }
    )
    request.session[SESSION_HISTORY_KEY] = history[-MAX_SESSION_HISTORY_ITEMS:]
    request.session.modified = True


def _load_persistent_history(user, limit: int) -> list[dict]:
    responses = (
        AssistantResponseLog.objects.select_related("question_log")
        .filter(question_log__user=user)
        .order_by("-created_at")[: max(1, limit)]
    )
    history = []
    for item in responses:
        payload = item.response_payload if isinstance(item.response_payload, dict) else {}
        history.append(
            {
                "question": item.question_log.question,
                "summary": item.summary or payload.get("summary", ""),
                "badges": payload.get("badges", []),
            }
        )
    return history


def _schedule_user_history_cleanup(user_id: int) -> None:
    key = f"assistente_lplan:cleanup:user:{user_id}"
    if not cache.add(key, "1", CLEANUP_USER_INTERVAL_SECONDS):
        return
    _cleanup_user_logs(user_id)


def _cleanup_user_logs(user_id: int) -> None:
    qs = AssistantQuestionLog.objects.filter(user_id=user_id)
    if LOG_RETENTION_DAYS > 0:
        cutoff = timezone.now() - timedelta(days=LOG_RETENTION_DAYS)
        qs.filter(created_at__lt=cutoff).delete()

    if MAX_LOGS_PER_USER <= 0:
        return

    keep_ids = list(qs.order_by("-created_at").values_list("id", flat=True)[:MAX_LOGS_PER_USER])
    if not keep_ids:
        return
    qs.exclude(id__in=keep_ids).delete()


def _build_question_cache_key(user_id: int, question: str, context: dict) -> str:
    normalized_q = (question or "").strip().lower()
    normalized_ctx = json.dumps(context or {}, sort_keys=True, ensure_ascii=False)
    hash_part = hashlib.sha256(f"{user_id}|{normalized_q}|{normalized_ctx}".encode("utf-8")).hexdigest()
    return f"assistente_lplan:q:{hash_part}"


def _normalize_response_payload(payload: dict) -> dict:
    """Garante campos esperados pelo frontend mesmo para cache legado."""
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("summary", "")
    payload.setdefault("radar_score", None)
    payload.setdefault("risk_level", "")
    payload.setdefault("trend", "")
    payload.setdefault("causes", [])
    payload.setdefault("recommended_action", {})
    payload.setdefault("secondary_actions", [])
    payload.setdefault("cards", [])
    payload.setdefault("table", {})
    payload.setdefault("badges", [])
    payload.setdefault("timeline", [])
    payload.setdefault("alerts", [])
    payload.setdefault("actions", [])
    payload.setdefault("links", [])
    payload.setdefault("raw_data", {})
    payload.setdefault("question_log_id", None)
    payload.setdefault("suggested_replies", [])
    return payload

