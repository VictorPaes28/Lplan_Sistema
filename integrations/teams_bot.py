import re
from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from accounts.groups import GRUPOS
from accounts.models import UserSignupRequest
from accounts.signup_services import approve_signup_request
from gestao_aprovacao.models import Approval, StatusHistory, WorkOrder
from integrations.models import IntegrationCommandLog

User = get_user_model()


@dataclass
class BotResult:
    ok: bool
    message: str
    command_name: str = ""
    payload: dict[str, Any] | None = None


def _is_approver(user) -> bool:
    if not user:
        return False
    if user.is_superuser or user.groups.filter(name=GRUPOS.ADMINISTRADOR).exists():
        return True
    return user.groups.filter(name=GRUPOS.APROVADOR).exists()


def _resolve_user(activity: dict[str, Any]):
    from_data = activity.get("from", {}) or {}
    candidates = []
    for key in ("userPrincipalName", "email"):
        if from_data.get(key):
            candidates.append(str(from_data.get(key)).strip().lower())
    aad = str(from_data.get("aadObjectId") or "").strip()
    if aad:
        candidates.append(aad.lower())
    for value in candidates:
        user = User.objects.filter(email__iexact=value).first()
        if user:
            return user, value
    return None, candidates[0] if candidates else ""


def _parse_command(raw_text: str) -> tuple[str, list[str]]:
    text = (raw_text or "").strip().lower()
    if not text:
        return "", []
    tokens = text.split()
    return tokens[0], tokens[1:]


def _find_workorder_by_ref(reference: str) -> WorkOrder | None:
    ref = (reference or "").strip()
    if not ref:
        return None
    if ref.isdigit():
        return WorkOrder.objects.filter(pk=int(ref)).first()
    return WorkOrder.objects.filter(codigo__iexact=ref).first()


def _approve_workorder(user, reference: str, comment: str) -> BotResult:
    if not _is_approver(user):
        return BotResult(ok=False, message="Você não possui permissão para aprovar pedidos.", command_name="aprovar_pedido")
    workorder = _find_workorder_by_ref(reference)
    if not workorder:
        return BotResult(ok=False, message=f"Pedido '{reference}' não encontrado.", command_name="aprovar_pedido")
    if not workorder.pode_aprovar(user):
        return BotResult(ok=False, message=f"Pedido {workorder.codigo} não está pendente para aprovação.", command_name="aprovar_pedido")
    with transaction.atomic():
        locked = WorkOrder.objects.select_for_update().get(pk=workorder.pk)
        if not locked.pode_aprovar(user):
            return BotResult(ok=False, message="Pedido já foi processado por outro aprovador.", command_name="aprovar_pedido")
        previous = locked.status
        Approval.objects.create(
            work_order=locked,
            aprovado_por=user,
            decisao="aprovado",
            comentario=comment or None,
        )
        locked.status = "aprovado"
        locked.data_aprovacao = timezone.now()
        locked.save(update_fields=["status", "data_aprovacao", "updated_at"])
        StatusHistory.objects.create(
            work_order=locked,
            status_anterior=previous,
            status_novo="aprovado",
            alterado_por=user,
            observacao=f"Aprovado via Teams. {comment}".strip(),
        )
    return BotResult(ok=True, message=f"Pedido {workorder.codigo} aprovado com sucesso via Teams.", command_name="aprovar_pedido", payload={"workorder_id": workorder.id})


def _reject_workorder(user, reference: str, comment: str) -> BotResult:
    if not _is_approver(user):
        return BotResult(ok=False, message="Você não possui permissão para reprovar pedidos.", command_name="reprovar_pedido")
    if not comment.strip():
        return BotResult(ok=False, message="Para reprovar, informe um motivo. Ex.: reprovar pedido 123 documento ausente", command_name="reprovar_pedido")
    workorder = _find_workorder_by_ref(reference)
    if not workorder:
        return BotResult(ok=False, message=f"Pedido '{reference}' não encontrado.", command_name="reprovar_pedido")
    if not workorder.pode_aprovar(user):
        return BotResult(ok=False, message=f"Pedido {workorder.codigo} não está pendente para reprovação.", command_name="reprovar_pedido")
    with transaction.atomic():
        locked = WorkOrder.objects.select_for_update().get(pk=workorder.pk)
        if not locked.pode_aprovar(user):
            return BotResult(ok=False, message="Pedido já foi processado por outro aprovador.", command_name="reprovar_pedido")
        previous = locked.status
        Approval.objects.create(
            work_order=locked,
            aprovado_por=user,
            decisao="reprovado",
            comentario=comment,
        )
        locked.status = "reprovado"
        locked.save(update_fields=["status", "updated_at"])
        StatusHistory.objects.create(
            work_order=locked,
            status_anterior=previous,
            status_novo="reprovado",
            alterado_por=user,
            observacao=f"Reprovado via Teams. Comentário: {comment}",
        )
    return BotResult(ok=True, message=f"Pedido {workorder.codigo} reprovado via Teams.", command_name="reprovar_pedido", payload={"workorder_id": workorder.id})


def _approve_signup(user, signup_id: str) -> BotResult:
    if not _is_approver(user):
        return BotResult(ok=False, message="Você não possui permissão para aprovar cadastros.", command_name="aprovar_cadastro")
    if not signup_id.isdigit():
        return BotResult(ok=False, message="Informe o ID numérico da solicitação de cadastro.", command_name="aprovar_cadastro")
    request_obj = UserSignupRequest.objects.filter(pk=int(signup_id)).first()
    if not request_obj:
        return BotResult(ok=False, message=f"Solicitação {signup_id} não encontrada.", command_name="aprovar_cadastro")
    if request_obj.status != UserSignupRequest.STATUS_PENDENTE:
        return BotResult(ok=False, message="Essa solicitação já foi processada.", command_name="aprovar_cadastro")
    created_user = approve_signup_request(request_obj, user)
    return BotResult(ok=True, message=f"Cadastro {request_obj.id} aprovado. Usuário criado: {created_user.username}.", command_name="aprovar_cadastro", payload={"signup_request_id": request_obj.id})


def _reject_signup(user, signup_id: str, reason: str) -> BotResult:
    if not _is_approver(user):
        return BotResult(ok=False, message="Você não possui permissão para rejeitar cadastros.", command_name="rejeitar_cadastro")
    if not signup_id.isdigit():
        return BotResult(ok=False, message="Informe o ID numérico da solicitação.", command_name="rejeitar_cadastro")
    if not reason.strip():
        return BotResult(ok=False, message="Informe o motivo da rejeição.", command_name="rejeitar_cadastro")
    request_obj = UserSignupRequest.objects.filter(pk=int(signup_id)).first()
    if not request_obj:
        return BotResult(ok=False, message=f"Solicitação {signup_id} não encontrada.", command_name="rejeitar_cadastro")
    if request_obj.status != UserSignupRequest.STATUS_PENDENTE:
        return BotResult(ok=False, message="Essa solicitação já foi processada.", command_name="rejeitar_cadastro")
    request_obj.status = UserSignupRequest.STATUS_REJEITADO
    request_obj.approved_by = user
    request_obj.rejected_at = timezone.now()
    request_obj.rejection_reason = reason
    request_obj.save(update_fields=["status", "approved_by", "rejected_at", "rejection_reason", "updated_at"])
    return BotResult(ok=True, message=f"Solicitação {request_obj.id} rejeitada via Teams.", command_name="rejeitar_cadastro", payload={"signup_request_id": request_obj.id})


def _pending_summary() -> str:
    pending_orders = WorkOrder.objects.filter(status__in=["pendente", "reaprovacao"]).count()
    pending_signup = UserSignupRequest.objects.filter(status=UserSignupRequest.STATUS_PENDENTE).count()
    return (
        "Pendências atuais:\n"
        f"- Pedidos pendentes/reaprovação: {pending_orders}\n"
        f"- Cadastros pendentes: {pending_signup}\n"
        "Comandos: pendencias | aprovar pedido <id|codigo> [comentario] | "
        "reprovar pedido <id|codigo> <motivo> | aprovar cadastro <id> | rejeitar cadastro <id> <motivo>"
    )


def process_teams_activity(activity: dict[str, Any]) -> BotResult:
    action_payload = activity.get("value") or {}
    if action_payload.get("action") == "approve_workorder":
        raw_text = f"aprovar pedido {action_payload.get('workorder') or ''} {action_payload.get('comment') or ''}".strip()
    elif action_payload.get("action") == "reject_workorder":
        raw_text = f"reprovar pedido {action_payload.get('workorder') or ''} {action_payload.get('comment') or ''}".strip()
    else:
        raw_text = (activity.get("text") or "").strip()
    user, external_identity = _resolve_user(activity)
    if not user:
        return BotResult(ok=False, message="Não foi possível mapear seu usuário do Teams para um usuário do sistema.", command_name="auth")
    command, args = _parse_command(raw_text)
    if command in ("help", "ajuda"):
        result = BotResult(ok=True, message=_pending_summary(), command_name="ajuda")
    elif command in ("pendencias", "pendência", "pendencia"):
        result = BotResult(ok=True, message=_pending_summary(), command_name="pendencias")
    elif command == "aprovar" and len(args) >= 2 and args[0] == "pedido":
        result = _approve_workorder(user, args[1], " ".join(args[2:]))
    elif command == "reprovar" and len(args) >= 2 and args[0] == "pedido":
        result = _reject_workorder(user, args[1], " ".join(args[2:]))
    elif command == "aprovar" and len(args) >= 2 and args[0] == "cadastro":
        result = _approve_signup(user, args[1])
    elif command in ("rejeitar", "reprovar") and len(args) >= 2 and args[0] == "cadastro":
        result = _reject_signup(user, args[1], " ".join(args[2:]))
    else:
        result = BotResult(ok=False, message="Comando não reconhecido. Digite 'ajuda'.", command_name="unknown")

    IntegrationCommandLog.objects.create(
        source="teams",
        command_text=raw_text,
        command_name=result.command_name,
        external_user_id=external_identity,
        external_user_email=user.email or "",
        actor=user,
        request_payload=activity,
        response_payload={"message": result.message, "ok": result.ok, "payload": result.payload or {}},
        success=result.ok,
    )
    return result

