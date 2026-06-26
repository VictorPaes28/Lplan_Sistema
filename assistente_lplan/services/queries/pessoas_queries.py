"""Perfil cruzado de pessoa / usuário."""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from assistente_lplan.services.permissions import AssistantPermissionService, UserScope

from . import pedidos_queries, restricoes_queries, trackhub_queries


def _resolve_user(user, scope: UserScope, perm: AssistantPermissionService, term: str):
    term = (term or "").strip()
    if not term:
        return user
    if scope.role == "admin":
        return User.objects.filter(
            Q(username__icontains=term)
            | Q(first_name__icontains=term)
            | Q(last_name__icontains=term)
            | Q(email__icontains=term)
        ).first()
    allowed = perm.allowed_user_ids_for_visibility(scope)
    u = (
        User.objects.filter(id__in=allowed)
        .filter(
            Q(username__icontains=term)
            | Q(first_name__icontains=term)
            | Q(last_name__icontains=term)
            | Q(email__icontains=term)
        )
        .first()
    )
    if u:
        return u
    return False


def perfil_usuario(user, scope: UserScope, perm: AssistantPermissionService, *, usuario_term: str = "") -> dict:
    target = _resolve_user(user, scope, perm, usuario_term)
    if target is False:
        return {"ok": False, "error": "usuario_fora_escopo"}
    if not target:
        return {"ok": False, "error": "usuario_nao_identificado"}

    since = timezone.now() - timedelta(days=30)
    from accounts.models import UserLoginLog
    from core.models import ConstructionDiary
    from gestao_aprovacao.models import Approval, WorkOrder

    name = target.get_full_name() or target.username
    diaries = ConstructionDiary.objects.filter(created_by=target, created_at__gte=since).count()
    pedidos = WorkOrder.objects.filter(criado_por=target, created_at__gte=since).count()
    aprovacoes = Approval.objects.filter(aprovado_por=target, created_at__gte=since).count()
    logins = UserLoginLog.objects.filter(user=target, created_at__gte=since).count()

    restr = restricoes_queries.restricoes_por_responsavel(
        user, scope, responsavel_nome=name.split()[0] if name else "", gerencial=True, limit_self=False
    )
    th = trackhub_queries.pendencias_por_responsavel(user, scope, responsavel_nome=name.split()[0] if name else "")

    ranking_restr = restr.get("ranking", [])
    me_restr = next((r for r in ranking_restr if r["responsavel"] == name), {"restricoes_abertas": 0, "vencidas": 0})
    ranking_th = th.get("ranking", [])
    me_th = next((r for r in ranking_th if r["responsavel"] == name), {"pendencias_vencidas": 0})

    return {
        "ok": True,
        "usuario": name,
        "logins_30d": logins,
        "diarios_30d": diaries,
        "pedidos_30d": pedidos,
        "aprovacoes_30d": aprovacoes,
        "restricoes_abertas": me_restr.get("restricoes_abertas", 0),
        "restricoes_vencidas": me_restr.get("vencidas", 0),
        "trackhub_vencidas": me_th.get("pendencias_vencidas", 0),
        "summary_hint": (
            f"Perfil de {name}: {diaries} diarios, {pedidos} pedidos, "
            f"{aprovacoes} aprovacoes nos ultimos 30 dias."
        ),
    }
