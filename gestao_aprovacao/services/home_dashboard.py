"""
Dados para a dashboard inicial do GestControll (escopo pessoal ou administrativo).

Mantém consultas enxutas e mesma regra de escopo da home legada (`queryset_workorders_home_scope`).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.db.models import Count, Prefetch, Q, DateTimeField
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from gestao_aprovacao.models import Approval, Comment, Empresa, Obra, WorkOrder, WorkOrderPermission

_REPROVACOES_PREFETCH = Prefetch(
    "approvals",
    queryset=Approval.objects.filter(decisao="reprovado")
    .prefetch_related("tags_erro")
    .order_by("-created_at"),
    to_attr="prefetched_reprovacoes",
)
from gestao_aprovacao.utils import (
    is_admin,
    is_aprovador,
    is_engenheiro,
    is_responsavel_empresa,
    usuario_pode_aprovar_pedido,
)


def _workorders_obras_ativas(qs):
    """Somente pedidos de obras ativas (``Obra.ativo`` espelha ``Project.is_active``)."""
    return qs.filter(obra__ativo=True)


def queryset_workorders_home_scope(user):
    """Pedidos relevantes por perfil — espelha a dashboard home original."""
    if is_admin(user):
        qs = WorkOrder.objects.select_related("obra", "obra__empresa", "criado_por").all()
    elif is_aprovador(user):
        obras_ids = Obra.objects.filter(
            id__in=WorkOrderPermission.objects.filter(
                usuario=user,
                tipo_permissao="aprovador",
                ativo=True,
            ).values_list("obra_id", flat=True),
            ativo=True,
        ).values_list("id", flat=True)
        empresas_ids = [
            e
            for e in Obra.objects.filter(id__in=obras_ids).values_list("empresa_id", flat=True).distinct()
            if e is not None
        ]
        obras_sem_empresa_ids = list(
            Obra.objects.filter(id__in=obras_ids, empresa_id__isnull=True).values_list("id", flat=True)
        )
        qs = WorkOrder.objects.filter(
            Q(obra__empresa_id__in=empresas_ids) | Q(obra_id__in=obras_sem_empresa_ids)
        ).select_related("obra", "obra__empresa", "criado_por")
    elif is_responsavel_empresa(user):
        empresas_resp = Empresa.objects.filter(responsavel=user, ativo=True)
        qs = WorkOrder.objects.filter(obra__empresa__in=empresas_resp).select_related(
            "obra", "obra__empresa", "criado_por"
        )
    elif is_engenheiro(user):
        obras_ids = Obra.objects.filter(
            id__in=WorkOrderPermission.objects.filter(
                usuario=user,
                tipo_permissao="solicitante",
                ativo=True,
            ).values_list("obra_id", flat=True),
            ativo=True,
        ).values_list("id", flat=True)
        if obras_ids:
            qs = (
                WorkOrder.objects.filter(Q(criado_por=user) | Q(obra_id__in=obras_ids))
                .select_related("obra", "obra__empresa", "criado_por")
                .distinct()
            )
        else:
            qs = WorkOrder.objects.filter(criado_por=user).select_related("obra", "obra__empresa", "criado_por")
    else:
        qs = WorkOrder.objects.filter(criado_por=user).select_related("obra", "obra__empresa", "criado_por")
    return _workorders_obras_ativas(qs)


# Lista unificada da home: prioridades no topo, depois recentes até o limite.
FEED_ITEMS_CAP = 18
FEED_RECENT_DAYS = 21
# Card "Motivos de reprovação" (somente não-aprovadores no template): ranking limitado na UI.
TAGS_RANK_VISIBLE_CAP = 6
# Card lateral: para aprovadores, lembrete de pedidos há muito tempo na fila (no lugar de tags).
APROVADOR_FILA_ATRASO_DIAS = 7
APROVADOR_FILA_ATRASO_MAX_ITENS = 20
APROVADOR_FILA_ATRASO_PDF_MAX_ITENS = 500
APROVADOR_FILA_CANDIDATES_SCAN = 500


def _format_valor_medicao(wo) -> str:
    if getattr(wo, "tipo_solicitacao", None) != "medicao" or wo.valor_medicao is None:
        return "—"
    v = wo.valor_medicao
    s = f"{v:.2f}"
    inteiro, dec = s.split(".", 1) if "." in s else (s, "00")
    neg = inteiro.startswith("-")
    if neg:
        inteiro = inteiro[1:]
    try:
        n = int(inteiro)
        inteiro_fmt = f"{n:,}".replace(",", ".")
    except ValueError:
        return f"R$ {v}"
    if neg:
        inteiro_fmt = "-" + inteiro_fmt
    return f"R$ {inteiro_fmt},{dec}"


def _format_ultimo_motivo_reprovacao(approval) -> str:
    if not approval:
        return "—"
    parts = []
    tags = list(approval.tags_erro.all())
    if tags:
        parts.append(", ".join(t.nome for t in tags))
    comentario = (approval.comentario or "").strip()
    if comentario:
        parts.append(comentario)
    return " | ".join(parts) if parts else "—"


def _local_month_start():
    d0 = timezone.localdate().replace(day=1)
    return timezone.make_aware(datetime.combine(d0, datetime.min.time()))


def _projects_with_active_fronts(project_ids) -> set[int]:
    if not project_ids:
        return set()
    from core.models import ProjectFront

    return set(
        ProjectFront.objects.filter(
            project_id__in=project_ids,
            is_active=True,
        ).values_list('project_id', flat=True).distinct()
    )


def _feed_front_fields(wo, *, admin_scope: bool, projects_with_fronts: set[int]) -> tuple[bool, str]:
    obra = getattr(wo, 'obra', None)
    project_id = getattr(obra, 'project_id', None) if obra else None
    if not project_id or project_id not in projects_with_fronts:
        return False, ''
    if getattr(wo, 'front_id', None):
        front = getattr(wo, 'front', None)
        return True, (front.name if front else '').strip() or 'Frente'
    if admin_scope:
        return True, 'Sem frente (obra toda)'
    return False, ''


def _feed_row_base(wo, *, admin_scope: bool, projects_with_fronts: set[int]) -> dict[str, Any]:
    mostrar_frente, front_label = _feed_front_fields(
        wo,
        admin_scope=admin_scope,
        projects_with_fronts=projects_with_fronts,
    )
    return {
        'pk': wo.pk,
        'codigo': wo.codigo,
        'obra_nome': wo.obra.nome if wo.obra_id else '',
        'mostrar_frente': mostrar_frente,
        'front_label': front_label,
        'status': wo.status,
        'status_display': wo.get_status_display(),
        'detail_url': reverse('gestao:detail_workorder', kwargs={'pk': wo.pk}),
        'updated_at': wo.updated_at,
    }


def collect_aprovador_fila_atraso(user, scoped_qs, *, limit: int | None = None) -> list[dict[str, Any]]:
    """
    Pedidos pendentes/reaprovação há mais de APROVADOR_FILA_ATRASO_DIAS dias
    (data de envio, ou criação se não houver envio), no escopo do usuário.
    """
    from gestao_aprovacao.utils import is_aprovador

    if not is_aprovador(user):
        return []

    now = timezone.now()
    cutoff_fila = now - timedelta(days=APROVADOR_FILA_ATRASO_DIAS)
    candidatos = (
        scoped_qs.filter(status__in=["pendente", "reaprovacao"])
        .annotate(wait_from=Coalesce("data_envio", "created_at", output_field=DateTimeField()))
        .filter(wait_from__lte=cutoff_fila)
        .select_related("obra", "obra__empresa", "criado_por")
        .prefetch_related(_REPROVACOES_PREFETCH)
        .order_by("wait_from")[:APROVADOR_FILA_CANDIDATES_SCAN]
    )

    pedidos: list[dict[str, Any]] = []
    for wo in candidatos:
        if not usuario_pode_aprovar_pedido(user, wo):
            continue
        wait_from = wo.wait_from
        dias_na_fila = max(0, (now - wait_from).days)
        solicitante = ""
        if wo.criado_por_id:
            solicitante = (wo.criado_por.get_full_name() or wo.criado_por.username or "").strip()
        reprovacoes = getattr(wo, "prefetched_reprovacoes", None) or []
        ultimo_motivo = _format_ultimo_motivo_reprovacao(reprovacoes[0] if reprovacoes else None)
        pedidos.append(
            {
                "pk": wo.pk,
                "codigo": wo.codigo,
                "obra_nome": wo.obra.nome if wo.obra_id else "",
                "obra_codigo": wo.obra.codigo if wo.obra_id else "",
                "empresa_nome": (wo.obra.empresa.nome if wo.obra_id and wo.obra.empresa_id else "") or "",
                "detail_url": reverse("gestao:detail_workorder", kwargs={"pk": wo.pk}),
                "dias_na_fila": dias_na_fila,
                "status": wo.status,
                "status_display": wo.get_status_display(),
                "tipo_solicitacao": wo.tipo_solicitacao,
                "tipo_solicitacao_display": wo.get_tipo_solicitacao_display(),
                "nome_credor": (wo.nome_credor or "").strip(),
                "valor_medicao": wo.valor_medicao,
                "valor_medicao_display": _format_valor_medicao(wo),
                "observacoes": (wo.observacoes or "").strip(),
                "wait_from": wait_from,
                "data_envio": wo.data_envio,
                "created_at": wo.created_at,
                "updated_at": wo.updated_at,
                "solicitante": solicitante,
                "qtd_reprovacoes": len(reprovacoes),
                "ultimo_motivo_reprovacao": ultimo_motivo,
            }
        )
        if limit is not None and len(pedidos) >= limit:
            break
    return pedidos


def _build_dashboard_context(user, scoped_qs, *, admin_scope: bool) -> dict[str, Any]:
    now = timezone.now()
    start_month = _local_month_start()
    mine = scoped_qs.filter(criado_por=user)
    agg_qs = scoped_qs if admin_scope else mine
    project_ids = set(
        scoped_qs.exclude(obra__project_id__isnull=True)
        .values_list('obra__project_id', flat=True)
        .distinct()
    )
    projects_with_fronts = _projects_with_active_fronts(project_ids)
    user_is_approver = is_aprovador(user) and not is_admin(user)

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
    if not admin_scope and user_is_approver:
        base = scoped_qs.filter(status__in=['pendente', 'reaprovacao']).annotate(
            ordem_dt=Coalesce('data_envio', 'created_at', output_field=DateTimeField())
        )
        for wo in base.select_related('obra', 'obra__empresa', 'front').order_by('ordem_dt', 'updated_at')[:40]:
            if usuario_pode_aprovar_pedido(user, wo):
                fila_aprovacao.append(wo)

    awaiting_my_approval_ct = len(fila_aprovacao)

    rows_by_pk: dict[int, dict[str, Any]] = {}

    def upsert_priority_row(wo, tipo: str, prio: int):
        existing = rows_by_pk.get(wo.pk)
        if existing is not None and existing['_prio'] <= prio:
            return
        row = _feed_row_base(
            wo,
            admin_scope=admin_scope,
            projects_with_fronts=projects_with_fronts,
        )
        row['tipo'] = tipo
        row['_prio'] = prio
        rows_by_pk[wo.pk] = row

    for wo in agg_qs.filter(status='reprovado').select_related('obra', 'front').order_by('-updated_at')[:8]:
        upsert_priority_row(wo, 'Pedido reprovado — ajustar e reenviar.', 20)

    for wo in agg_qs.filter(status='reaprovacao').select_related('obra', 'front').order_by('-updated_at')[:8]:
        upsert_priority_row(wo, 'Em reaprovação — verifique pendências e anexos.', 30)

    cutoff_cm = now - timedelta(days=5)
    comment_qs = Comment.objects.filter(
        origem=Comment.Origem.USUARIO,
        created_at__gte=cutoff_cm,
        work_order__obra__ativo=True,
    ).exclude(autor_id=user.pk).exclude(work_order__status='rascunho')
    if admin_scope:
        comment_qs = comment_qs.filter(work_order__in=scoped_qs)
    else:
        comment_qs = comment_qs.filter(work_order__criado_por=user)

    for c in comment_qs.select_related('work_order', 'work_order__obra', 'work_order__front').order_by('-created_at')[:25]:
        wo = c.work_order
        quem = (c.autor.get_full_name() or c.autor.username) if c.autor else 'outro usuário'
        upsert_priority_row(wo, f'Comentário recente ({quem}).', 35)

    stale_before = now - timedelta(days=14)
    for wo in (
        agg_qs.filter(status__in=['pendente', 'reaprovacao'], updated_at__lt=stale_before)
        .select_related('obra', 'front')
        .order_by('updated_at')[:10]
    ):
        if user_is_approver and usuario_pode_aprovar_pedido(user, wo):
            continue
        upsert_priority_row(wo, 'Pedido há bastante tempo sem atualização.', 70)

    if not admin_scope:
        for wo in fila_aprovacao[:12]:
            upsert_priority_row(wo, 'Pedido na sua fila para aprovação.', 15)
    else:
        base = scoped_qs.filter(status__in=['pendente', 'reaprovacao']).annotate(
            ordem_dt=Coalesce('data_envio', 'created_at', output_field=DateTimeField())
        )
        for wo in base.select_related('obra', 'obra__empresa', 'front').order_by('ordem_dt', 'updated_at')[:12]:
            upsert_priority_row(wo, 'Pedido na fila de aprovação (aguardando decisão).', 16)

    rows = list(rows_by_pk.values())
    rows.sort(key=lambda r: (r['_prio'], -r['updated_at'].timestamp()))
    for r in rows:
        del r['_prio']

    prioridade_linhas = rows[:FEED_ITEMS_CAP]
    pks_pri = {r['pk'] for r in prioridade_linhas}

    slack = FEED_ITEMS_CAP - len(prioridade_linhas)
    data_limite_feed = now - timedelta(days=FEED_RECENT_DAYS)
    dash_feed: list[dict[str, Any]] = []
    for r in prioridade_linhas:
        dash_feed.append(
            {
                'pk': r['pk'],
                'codigo': r['codigo'],
                'obra_nome': r['obra_nome'],
                'mostrar_frente': r['mostrar_frente'],
                'front_label': r['front_label'],
                'status': r['status'],
                'status_display': r['status_display'],
                'detail_url': r['detail_url'],
                'updated_at': r['updated_at'],
                'prioridade': True,
                'prioridade_hint': r['tipo'],
            }
        )

    if slack > 0:
        for wo in (
            scoped_qs.filter(updated_at__gte=data_limite_feed)
            .exclude(pk__in=pks_pri)
            .exclude(status='rascunho')
            .select_related('obra', 'front')
            .order_by('-updated_at')[:slack]
        ):
            row = _feed_row_base(
                wo,
                admin_scope=admin_scope,
                projects_with_fronts=projects_with_fronts,
            )
            dash_feed.append(
                {
                    **row,
                    'prioridade': False,
                    'prioridade_hint': '',
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
        todos_atraso = collect_aprovador_fila_atraso(user, scoped_qs)
        pedidos_atraso = todos_atraso[:APROVADOR_FILA_ATRASO_MAX_ITENS]

        dash_aprovador_fila_atraso = {
            "dias_limite": APROVADOR_FILA_ATRASO_DIAS,
            "pedidos": pedidos_atraso,
            "total_na_fila": len(todos_atraso),
            "link_pendentes": dash_quick_links["pendentes"],
            "pdf_url": reverse("gestao:export_fila_atraso_pdf"),
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
        "feed_recent_days": FEED_RECENT_DAYS,
        "dash_tags_reprovacao": dash_tags_reprovacao,
        "dash_tags_meta": dash_tags_meta,
        "dash_quick_links": dash_quick_links,
        "dash_aprovador_fila_atraso": dash_aprovador_fila_atraso,
    }


def build_personal_dashboard_context(user, scoped_qs) -> dict[str, Any]:
    return _build_dashboard_context(user, scoped_qs, admin_scope=False)


def build_admin_dashboard_context(user, scoped_qs) -> dict[str, Any]:
    return _build_dashboard_context(user, scoped_qs, admin_scope=True)
