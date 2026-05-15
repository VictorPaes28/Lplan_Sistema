"""
Dados para a dashboard inicial do GestControll (escopo pessoal ou administrativo).

Mantém consultas enxutas e mesma regra de escopo da home legada (`queryset_workorders_home_scope`).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.db.models import Count, Q, DateTimeField
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from gestao_aprovacao.models import Approval, Comment, Empresa, Obra, WorkOrder, WorkOrderPermission
from gestao_aprovacao.utils import is_admin, is_aprovador, is_engenheiro, is_responsavel_empresa


def queryset_workorders_home_scope(user):
    """Pedidos relevantes por perfil — espelha a dashboard home original."""
    if is_admin(user):
        return WorkOrder.objects.select_related("obra", "obra__empresa", "criado_por").all()
    if is_aprovador(user):
        obras_ids = WorkOrderPermission.objects.filter(
            usuario=user,
            tipo_permissao="aprovador",
            ativo=True,
        ).values_list("obra_id", flat=True).distinct()
        empresas_ids = [
            e
            for e in Obra.objects.filter(id__in=obras_ids).values_list("empresa_id", flat=True).distinct()
            if e is not None
        ]
        obras_sem_empresa_ids = list(
            Obra.objects.filter(id__in=obras_ids, empresa_id__isnull=True).values_list("id", flat=True)
        )
        return WorkOrder.objects.filter(
            Q(obra__empresa_id__in=empresas_ids) | Q(obra_id__in=obras_sem_empresa_ids)
        ).select_related("obra", "obra__empresa", "criado_por")
    if is_responsavel_empresa(user):
        empresas_resp = Empresa.objects.filter(responsavel=user, ativo=True)
        return WorkOrder.objects.filter(obra__empresa__in=empresas_resp).select_related(
            "obra", "obra__empresa", "criado_por"
        )
    if is_engenheiro(user):
        obras_ids = WorkOrderPermission.objects.filter(
            usuario=user,
            tipo_permissao="solicitante",
            ativo=True,
        ).values_list("obra_id", flat=True).distinct()
        if obras_ids:
            return (
                WorkOrder.objects.filter(Q(criado_por=user) | Q(obra_id__in=obras_ids))
                .select_related("obra", "obra__empresa", "criado_por")
                .distinct()
            )
    return WorkOrder.objects.filter(criado_por=user).select_related("obra", "obra__empresa", "criado_por")


# Lista unificada da home: prioridades no topo, depois recentes até o limite.
FEED_ITEMS_CAP = 18
FEED_RECENT_DAYS = 21
# Card "Motivos de reprovação" (somente não-aprovadores no template): ranking limitado na UI.
TAGS_RANK_VISIBLE_CAP = 6
# Card lateral: para aprovadores, lembrete de pedidos há muito tempo na fila (no lugar de tags).
APROVADOR_FILA_ATRASO_DIAS = 15
APROVADOR_FILA_ATRASO_MAX_ITENS = 20
APROVADOR_FILA_CANDIDATES_SCAN = 120


def _local_month_start():
    d0 = timezone.localdate().replace(day=1)
    return timezone.make_aware(datetime.combine(d0, datetime.min.time()))


def _build_dashboard_context(user, scoped_qs, *, admin_scope: bool) -> dict[str, Any]:
    now = timezone.now()
    start_month = _local_month_start()
    mine = scoped_qs.filter(criado_por=user)
    agg_qs = scoped_qs if admin_scope else mine

    criados_mes = agg_qs.filter(created_at__gte=start_month).count()

    aprovados_mes = agg_qs.filter(
        status="aprovado",
        data_aprovacao__isnull=False,
        data_aprovacao__gte=start_month,
    ).count()

    reprov_eventos_distintos_mes = (
        Approval.objects.filter(
            decisao="reprovado",
            created_at__gte=start_month,
            work_order__in=agg_qs,
        )
        .values("work_order_id")
        .distinct()
        .count()
    )

    pendente_equipe_aguarda = agg_qs.filter(status__in=["pendente", "reaprovacao"]).count()
    solicitante_deve_agir = agg_qs.filter(status__in=["rascunho", "reprovado", "reaprovacao"]).count()

    fila_aprovacao: list[WorkOrder] = []
    if not admin_scope and is_aprovador(user) and not is_admin(user):
        base = scoped_qs.filter(status__in=["pendente", "reaprovacao"]).annotate(
            ordem_dt=Coalesce("data_envio", "created_at", output_field=DateTimeField())
        )
        for wo in base.order_by("ordem_dt", "updated_at")[:40]:
            if wo.pode_aprovar(user):
                fila_aprovacao.append(wo)

    awaiting_my_approval_ct = len(fila_aprovacao)

    rows: list[dict[str, Any]] = []
    seen: set[int] = set()

    def append_row(wo, tipo, prio):
        if wo.pk in seen:
            return
        seen.add(wo.pk)
        rows.append(
            {
                "pk": wo.pk,
                "codigo": wo.codigo,
                "obra_nome": wo.obra.nome if wo.obra_id else "",
                "status": wo.status,
                "status_display": wo.get_status_display(),
                "tipo": tipo,
                "_prio": prio,
                "detail_url": reverse("gestao:detail_workorder", kwargs={"pk": wo.pk}),
                "updated_at": wo.updated_at,
            }
        )

    for wo in agg_qs.filter(status="rascunho").order_by("-updated_at")[:8]:
        append_row(wo, "Finalize o envio (rascunho).", 10)

    for wo in agg_qs.filter(status="reprovado").order_by("-updated_at")[:8]:
        append_row(wo, "Pedido reprovado — ajustar e reenviar.", 20)

    for wo in agg_qs.filter(status="reaprovacao").order_by("-updated_at")[:8]:
        append_row(wo, "Em reaprovação — verifique pendências e anexos.", 30)

    cutoff_cm = now - timedelta(days=5)
    comment_qs = Comment.objects.filter(
        origem=Comment.Origem.USUARIO,
        created_at__gte=cutoff_cm,
    ).exclude(autor_id=user.pk)
    if admin_scope:
        comment_qs = comment_qs.filter(work_order__in=scoped_qs)
    else:
        comment_qs = comment_qs.filter(work_order__criado_por=user)

    for c in comment_qs.select_related("work_order", "work_order__obra").order_by("-created_at")[:25]:
        wo = c.work_order
        quem = (c.autor.get_full_name() or c.autor.username) if c.autor else "outro usuário"
        append_row(wo, f"Comentário recente ({quem}).", 35)

    stale_before = now - timedelta(days=14)
    for wo in (
        agg_qs.filter(status__in=["pendente", "reaprovacao"], updated_at__lt=stale_before).order_by("updated_at")[:10]
    ):
        append_row(wo, "Pedido há bastante tempo sem atualização.", 70)

    if not admin_scope:
        for wo in fila_aprovacao[:12]:
            append_row(wo, "Pedido na sua fila para aprovação.", 15)
    else:
        base = scoped_qs.filter(status__in=["pendente", "reaprovacao"]).annotate(
            ordem_dt=Coalesce("data_envio", "created_at", output_field=DateTimeField())
        )
        for wo in base.order_by("ordem_dt", "updated_at")[:12]:
            append_row(wo, "Pedido na fila de aprovação (aguardando decisão).", 16)

    rows.sort(key=lambda r: (r["_prio"], -r["updated_at"].timestamp()))
    for r in rows:
        del r["_prio"]

    prioridade_linhas = rows[:FEED_ITEMS_CAP]
    pks_pri = {r["pk"] for r in prioridade_linhas}

    slack = FEED_ITEMS_CAP - len(prioridade_linhas)
    data_limite_feed = now - timedelta(days=FEED_RECENT_DAYS)
    dash_feed: list[dict[str, Any]] = []
    for r in prioridade_linhas:
        dash_feed.append(
            {
                "pk": r["pk"],
                "codigo": r["codigo"],
                "obra_nome": r["obra_nome"],
                "status": r["status"],
                "status_display": r["status_display"],
                "detail_url": r["detail_url"],
                "updated_at": r["updated_at"],
                "prioridade": True,
                "prioridade_hint": r["tipo"],
            }
        )

    if slack > 0:
        for wo in (
            scoped_qs.filter(updated_at__gte=data_limite_feed).exclude(pk__in=pks_pri).order_by("-updated_at")[:slack]
        ):
            dash_feed.append(
                {
                    "pk": wo.pk,
                    "codigo": wo.codigo,
                    "obra_nome": wo.obra.nome if wo.obra_id else "",
                    "status": wo.status,
                    "status_display": wo.get_status_display(),
                    "detail_url": reverse("gestao:detail_workorder", kwargs={"pk": wo.pk}),
                    "updated_at": wo.updated_at,
                    "prioridade": False,
                    "prioridade_hint": "",
                }
            )

    for i in range(len(dash_feed)):
        row = dash_feed[i]
        if not row["prioridade"] and i > 0 and dash_feed[i - 1]["prioridade"]:
            row["mostrar_sep_recentes"] = True

    lista_base = reverse("gestao:list_workorders")
    meus_param = str(user.pk)

    if admin_scope:
        dash_quick_links = {
            "lista_todos": lista_base,
            "pendentes": f"{lista_base}?status=pendente",
            "reprovados": f"{lista_base}?status=reprovado",
            "rascunhos": f"{lista_base}?status=rascunho",
            "periodo_30": f"{lista_base}?periodo_rapido=30",
        }
    else:
        if is_aprovador(user):
            pend_url = f"{lista_base}?status=pendente"
        else:
            pend_url = f"{lista_base}?status=pendente&engenheiro={meus_param}"
        dash_quick_links = {
            "lista_todos": lista_base,
            "pendentes": pend_url,
            "reprovados": f"{lista_base}?status=reprovado&engenheiro={meus_param}",
            "rascunhos": f"{lista_base}?status=rascunho&engenheiro={meus_param}",
            "periodo_30": f"{lista_base}?periodo_rapido=30&engenheiro={meus_param}",
        }

    dash_aprovador_fila_atraso: dict[str, Any] | None = None
    dash_tags_meta: dict[str, Any]
    dash_tags_reprovacao: list[dict[str, Any]]

    if is_aprovador(user):
        cutoff_fila = now - timedelta(days=APROVADOR_FILA_ATRASO_DIAS)
        candidatos = (
            scoped_qs.filter(status__in=["pendente", "reaprovacao"])
            .annotate(wait_from=Coalesce("data_envio", "created_at", output_field=DateTimeField()))
            .filter(wait_from__lte=cutoff_fila)
            .select_related("obra")
            .order_by("wait_from")[:APROVADOR_FILA_CANDIDATES_SCAN]
        )
        pedidos_atraso: list[dict[str, Any]] = []
        for wo in candidatos:
            if not wo.pode_aprovar(user):
                continue
            dias_na_fila = max(0, (now - wo.wait_from).days)
            pedidos_atraso.append(
                {
                    "pk": wo.pk,
                    "codigo": wo.codigo,
                    "obra_nome": wo.obra.nome if wo.obra_id else "",
                    "detail_url": reverse("gestao:detail_workorder", kwargs={"pk": wo.pk}),
                    "dias_na_fila": dias_na_fila,
                    "status_display": wo.get_status_display(),
                }
            )
            if len(pedidos_atraso) >= APROVADOR_FILA_ATRASO_MAX_ITENS:
                break

        dash_aprovador_fila_atraso = {
            "dias_limite": APROVADOR_FILA_ATRASO_DIAS,
            "pedidos": pedidos_atraso,
            "link_pendentes": dash_quick_links["pendentes"],
        }
        dash_tags_meta = {
            "reprovacoes_total": 0,
            "reprovacoes_com_tag": 0,
            "ranking_truncado": False,
            "ranking_mostrar_top": TAGS_RANK_VISIBLE_CAP,
        }
        dash_tags_reprovacao = []
    else:
        dash_aprovador_fila_atraso = None
        tag_cutoff = now - timedelta(days=365)
        tag_pedidos_qs = scoped_qs if admin_scope else mine

        qs_reprov_tag = Approval.objects.filter(
            work_order__in=tag_pedidos_qs,
            decisao="reprovado",
            created_at__gte=tag_cutoff,
        )
        dash_tags_meta = {
            "reprovacoes_total": qs_reprov_tag.count(),
            "reprovacoes_com_tag": qs_reprov_tag.filter(tags_erro__pk__isnull=False)
            .values("id")
            .distinct()
            .count(),
            "ranking_truncado": False,
            "ranking_mostrar_top": TAGS_RANK_VISIBLE_CAP,
        }

        tag_rank_qs = (
            Approval.objects.filter(
                work_order__in=tag_pedidos_qs,
                decisao="reprovado",
                created_at__gte=tag_cutoff,
                tags_erro__pk__isnull=False,
            )
            .values("tags_erro__id", "tags_erro__nome")
            .annotate(uso_count=Count("id", distinct=True))
            .order_by("-uso_count", "tags_erro__nome")
        )

        tag_rank_fetched = list(tag_rank_qs[: TAGS_RANK_VISIBLE_CAP + 1])
        dash_tags_meta["ranking_truncado"] = len(tag_rank_fetched) > TAGS_RANK_VISIBLE_CAP
        tag_rank_rows = tag_rank_fetched[:TAGS_RANK_VISIBLE_CAP]
        max_uso = max((r["uso_count"] for r in tag_rank_rows), default=1)
        dash_tags_reprovacao = [
            {
                "nome": r["tags_erro__nome"] or "",
                "count": r["uso_count"],
                "bar_pct": min(100, round(100.0 * r["uso_count"] / max_uso)),
            }
            for r in tag_rank_rows
        ]

    return {
        "dash_escopo_admin": admin_scope,
        "dash_period_note": timezone.localdate().strftime("%m/%Y"),
        "dash_kpis": {
            "criados_mes": criados_mes,
            "aprovados_mes": aprovados_mes,
            "reprovados_pedidos_distintos_mes": reprov_eventos_distintos_mes,
            "pedidos_aguardando_aprovadores": pendente_equipe_aguarda,
            "precisa_agir_como_solicitante": solicitante_deve_agir,
            "aguardando_sua_analise": awaiting_my_approval_ct,
            "tem_fila_aprovador": bool(fila_aprovacao) if not admin_scope else False,
        },
        "dash_feed": dash_feed,
        "dash_tags_reprovacao": dash_tags_reprovacao,
        "dash_tags_meta": dash_tags_meta,
        "dash_quick_links": dash_quick_links,
        "dash_aprovador_fila_atraso": dash_aprovador_fila_atraso,
    }


def build_personal_dashboard_context(user, scoped_qs) -> dict[str, Any]:
    return _build_dashboard_context(user, scoped_qs, admin_scope=False)


def build_admin_dashboard_context(user, scoped_qs) -> dict[str, Any]:
    return _build_dashboard_context(user, scoped_qs, admin_scope=True)
