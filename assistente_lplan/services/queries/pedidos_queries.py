"""Consultas GestControll / pedidos."""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from gestao_aprovacao.models import Approval, WorkOrder

from assistente_lplan.services.permissions import UserScope

from ._scope import LIMITE_LISTA, resolve_obra_gestao, resolve_project


def _work_orders_scope(user, scope: UserScope):
    qs = WorkOrder.objects.all()
    if scope.role == "admin":
        return qs
    if scope.role == "aprovador":
        return qs.filter(obra_id__in=scope.aprovador_obra_ids).distinct()
    return qs.filter(criado_por=user).distinct()


def _dias_em_aberto(workorder, hoje=None):
    hoje = hoje or timezone.localdate()
    if not workorder.data_envio:
        return None
    return max((hoje - workorder.data_envio.date()).days, 0)


def _serializar_pedido(w, hoje=None):
    hoje = hoje or timezone.localdate()
    dias = _dias_em_aberto(w, hoje)
    return {
        "pedido": w.codigo,
        "obra": w.obra.nome if w.obra else "-",
        "solicitante": (w.criado_por.get_full_name() or w.criado_por.username) if w.criado_por else "-",
        "tipo": w.tipo_solicitacao,
        "data": w.created_at.strftime("%d/%m/%Y"),
        "dias_em_aberto": dias if dias is not None else "-",
        "status": w.status,
    }


def pedidos_pendentes(user, scope: UserScope, *, project=None, obra: str = "") -> dict:
    qs = _work_orders_scope(user, scope).filter(status__in=["pendente", "reaprovacao"]).select_related("obra", "criado_por")
    if project:
        qs = qs.filter(obra__project_id=project.id)
    elif obra:
        og = resolve_obra_gestao(scope, obra=obra)
        if og:
            qs = qs.filter(obra=og)
    total = qs.count()
    rows = [_serializar_pedido(w) for w in qs.order_by("-created_at")[:30]]
    return {
        "ok": True,
        "total": total,
        "rows": rows,
        "summary_hint": f"{total} pedido(s) pendentes de aprovacao no seu escopo.",
    }


def pedidos_atrasados(user, scope: UserScope, *, dias_limite: int = 7, project=None, obra: str = "") -> dict:
    hoje = timezone.localdate()
    qs = _work_orders_scope(user, scope).filter(status__in=["pendente", "reaprovacao"]).select_related("obra", "criado_por")
    if project:
        qs = qs.filter(obra__project_id=project.id)
    elif obra:
        og = resolve_obra_gestao(scope, obra=obra)
        if og:
            qs = qs.filter(obra=og)
    atrasados = []
    for w in qs:
        dias = _dias_em_aberto(w, hoje)
        if dias is not None and dias >= dias_limite:
            row = _serializar_pedido(w, hoje)
            row["dias_em_aberto"] = dias
            atrasados.append(row)
    atrasados.sort(key=lambda x: x.get("dias_em_aberto", 0), reverse=True)
    return {
        "ok": True,
        "total": len(atrasados),
        "dias_limite": dias_limite,
        "rows": atrasados[:30],
        "summary_hint": f"{len(atrasados)} pedido(s) parados ha {dias_limite}+ dias.",
    }


def pedidos_reprovados(user, scope: UserScope, *, project=None) -> dict:
    scoped = _work_orders_scope(user, scope)
    qs = (
        Approval.objects.select_related("work_order", "work_order__obra", "aprovado_por")
        .filter(decisao="reprovado", work_order__in=scoped)
        .order_by("-created_at")
    )
    if project:
        qs = qs.filter(work_order__obra__project_id=project.id)
    rows = []
    for item in qs[:30]:
        rows.append(
            {
                "pedido": item.work_order.codigo if item.work_order else "-",
                "obra": item.work_order.obra.nome if item.work_order and item.work_order.obra else "-",
                "aprovador": (item.aprovado_por.get_full_name() or item.aprovado_por.username)
                if item.aprovado_por
                else "-",
                "data": item.created_at.strftime("%d/%m/%Y %H:%M"),
                "motivo": (item.comentario or "")[:120],
            }
        )
    return {
        "ok": True,
        "total": len(rows),
        "rows": rows,
        "summary_hint": f"{len(rows)} reprovacoes recentes localizadas.",
    }


def pedidos_por_aprovador(user, scope: UserScope, *, usuario_term: str = "") -> dict:
    from django.contrib.auth.models import User

    qs = _work_orders_scope(user, scope).filter(status__in=["pendente", "reaprovacao"]).select_related("obra", "criado_por")
    rows = [_serializar_pedido(w) for w in qs.order_by("-created_at")[:30]]
    aprovador_nome = ""
    if usuario_term:
        u = User.objects.filter(
            Q(username__icontains=usuario_term)
            | Q(first_name__icontains=usuario_term)
            | Q(last_name__icontains=usuario_term)
        ).first()
        if u:
            aprovador_nome = u.get_full_name() or u.username
    return {
        "ok": True,
        "total": qs.count(),
        "aprovador": aprovador_nome or (user.get_full_name() or user.username),
        "rows": rows,
        "summary_hint": f"{qs.count()} pedido(s) na fila de aprovacao.",
    }


def quick_pedidos_atrasados_count(user, scope: UserScope, dias_limite: int = 7) -> int:
    data = pedidos_atrasados(user, scope, dias_limite=dias_limite)
    return int(data.get("total", 0))
