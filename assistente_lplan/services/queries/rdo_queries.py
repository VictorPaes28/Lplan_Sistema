"""Consultas de RDO / Diário de Obra."""
from __future__ import annotations

from datetime import date, timedelta

from django.utils import timezone

from core.kpi_queries import count_diarios_aguardando_gestor
from core.models import ConstructionDiary, DiaryNoReportDay, DiaryStatus, Project

from assistente_lplan.services.permissions import AssistantPermissionService, UserScope

from ._scope import LIMITE_LISTA, project_ids, projects_qs, resolve_project


def _calcular_lacunas_rdo(datas: list, lacuna_minima_dias: int = 7):
    if len(datas) < 2:
        return 0, []
    maior = 0
    lacunas = []
    for i in range(1, len(datas)):
        gap = (datas[i] - datas[i - 1]).days
        if gap >= lacuna_minima_dias:
            maior = max(maior, gap)
            lacunas.append(
                {
                    "apos_data": str(datas[i - 1]),
                    "antes_data": str(datas[i]),
                    "dias_sem_rdo": gap,
                }
            )
    return maior, lacunas


def _metricas_rdo_frequencia(project, front_id=None, dias_analise=90, dias_sem_rdo_alerta=7, lacuna_minima_dias=7):
    hoje = timezone.localdate()
    inicio_periodo = hoje - timedelta(days=dias_analise)
    qs_all = ConstructionDiary.objects.filter(project=project)
    qs_periodo = qs_all.filter(date__gte=inicio_periodo, date__lte=hoje)

    if front_id == "todas":
        pass
    elif front_id is None:
        qs_all = qs_all.filter(front__isnull=True)
        qs_periodo = qs_periodo.filter(front__isnull=True)
    else:
        qs_all = qs_all.filter(front_id=front_id)
        qs_periodo = qs_periodo.filter(front_id=front_id)

    datas_all = sorted(set(qs_all.values_list("date", flat=True)))
    datas_periodo = sorted(set(qs_periodo.values_list("date", flat=True)))
    nunca_teve = len(datas_all) == 0
    ultimo = datas_all[-1] if datas_all else None
    dias_desde_ultimo = (hoje - ultimo).days if ultimo else None
    maior_lacuna, lacunas = _calcular_lacunas_rdo(datas_periodo, lacuna_minima_dias)

    return {
        "ultimo_rdo_data": str(ultimo) if ultimo else None,
        "dias_desde_ultimo": dias_desde_ultimo,
        "total_rdos_periodo": len(datas_periodo),
        "maior_intervalo_sem_rdo_dias": maior_lacuna,
        "lacunas_no_periodo": lacunas,
        "qtd_lacunas_no_periodo": len(lacunas),
        "nunca_teve_rdo": nunca_teve,
        "sem_rdo_recente": dias_desde_ultimo is not None and dias_desde_ultimo > dias_sem_rdo_alerta,
    }


def _frentes_ativas_project(project: Project):
    from core.models import ProjectFront

    return list(ProjectFront.objects.filter(project=project, is_active=True).order_by("name"))


def rdos_pendentes_aprovacao(user, scope: UserScope, *, data: date | None = None) -> dict:
    data = data or timezone.localdate()
    pids = project_ids(scope)
    qs = ConstructionDiary.objects.filter(
        status=DiaryStatus.AGUARDANDO_APROVACAO_GESTOR,
        date=data,
        project__is_active=True,
        project_id__in=pids,
    ).select_related("project")
    rows = [{"obra": d.project.name, "codigo": d.project.code, "data": str(d.date)} for d in qs[:LIMITE_LISTA]]
    return {
        "ok": True,
        "total": qs.count(),
        "data": str(data),
        "rows": rows,
        "summary_hint": f"{qs.count()} RDO(s) aguardando aprovacao do gestor em {data.strftime('%d/%m/%Y')}.",
    }


def rdos_por_data(user, scope: UserScope, *, target_date: date, project: Project | None = None) -> dict:
    qs = ConstructionDiary.objects.select_related("project", "created_by").filter(date=target_date)
    if project:
        qs = qs.filter(project=project)
    else:
        qs = qs.filter(project_id__in=project_ids(scope))
    rows = []
    for d in qs.order_by("project__code")[:LIMITE_LISTA]:
        rows.append(
            {
                "obra": d.project.code if d.project else "-",
                "projeto": d.project.name if d.project else "-",
                "data": d.date.strftime("%d/%m/%Y") if d.date else "-",
                "rdo": f"#{d.report_number}" if d.report_number else "-",
                "status": d.get_status_display(),
                "responsavel": (d.created_by.get_full_name() or d.created_by.username) if d.created_by else "-",
            }
        )
    return {
        "ok": True,
        "total": len(rows),
        "data": target_date.isoformat(),
        "rows": rows,
        "summary_hint": f"{len(rows)} registro(s) de diario em {target_date.strftime('%d/%m/%Y')}.",
    }


def obras_sem_rdo(user, scope: UserScope, *, data: date | None = None) -> dict:
    data = data or timezone.localdate()
    hoje = timezone.localdate()
    sem_hoje = []
    nunca = []
    for project in projects_qs(scope)[:LIMITE_LISTA]:
        tem_hoje = ConstructionDiary.objects.filter(project=project, date=data).exists()
        if not tem_hoje:
            sem_hoje.append({"obra": project.name, "codigo": project.code})
        if not ConstructionDiary.objects.filter(project=project).exists():
            nunca.append({"obra": project.name, "codigo": project.code})
    return {
        "ok": True,
        "data": str(data),
        "sem_rdo_na_data": sem_hoje,
        "nunca_teve_rdo": nunca,
        "summary_hint": (
            f"{len(sem_hoje)} obra(s) sem RDO em {data.strftime('%d/%m/%Y')}; "
            f"{len(nunca)} nunca registraram diario."
        ),
    }


def frequencia_rdos(user, scope: UserScope, *, project: Project | None = None, obra: str = "") -> dict:
    if not project:
        project = resolve_project(scope, obra=obra)
    if not project:
        projects = list(projects_qs(scope)[:LIMITE_LISTA])
        obras_out = []
        for p in projects:
            m = _metricas_rdo_frequencia(p, front_id="todas")
            obras_out.append({"obra": p.name, "codigo": p.code, **m})
        return {
            "ok": True,
            "multi": True,
            "obras": obras_out,
            "summary_hint": f"Frequencia de RDO em {len(obras_out)} obra(s) do seu escopo.",
        }

    frentes = _frentes_ativas_project(project)
    segmentos = []
    if frentes:
        configs = [(None, "Obra inteira")] + [(f.id, f.name) for f in frentes]
        for front_id, nome in configs:
            segmentos.append({"frente": nome, **_metricas_rdo_frequencia(project, front_id=front_id)})
    else:
        segmentos.append({"frente": "Obra", **_metricas_rdo_frequencia(project, front_id="todas")})

    return {
        "ok": True,
        "obra": project.name,
        "codigo": project.code,
        "segmentos": segmentos,
        "summary_hint": f"Frequencia de RDO da obra {project.code}.",
    }


def frentes_obra(user, scope: UserScope, *, project: Project | None = None, obra: str = "") -> dict:
    project = project or resolve_project(scope, obra=obra)
    if not project:
        return {"ok": False, "error": "obra_nao_encontrada"}
    from gestao_aprovacao.models import Obra as ObraGestao

    obra_g = ObraGestao.objects.filter(project=project, ativo=True).first()
    frentes = _frentes_ativas_project(project)
    hoje = timezone.localdate()
    rows = []
    for front in frentes or [None]:
        fid = front.id if front else None
        m = _metricas_rdo_frequencia(project, front_id=fid if front else None)
        pend = 0
        if obra_g:
            from gestao_aprovacao.models import WorkOrder

            qs = WorkOrder.objects.filter(obra=obra_g, status__in=["pendente", "reaprovacao"])
            qs = qs.filter(front_id=fid) if front else qs.filter(front__isnull=True)
            pend = qs.count()
        rows.append(
            {
                "frente": front.name if front else "Obra inteira",
                "ultimo_rdo": m.get("ultimo_rdo_data") or "-",
                "dias_desde_ultimo": m.get("dias_desde_ultimo"),
                "pedidos_pendentes": pend,
                "lacunas": m.get("qtd_lacunas_no_periodo", 0),
            }
        )
    return {
        "ok": True,
        "obra": project.name,
        "codigo": project.code,
        "rows": rows,
        "summary_hint": f"Resumo de {len(rows)} frente(s) na obra {project.code}.",
    }


def quick_rdo_pendentes_count(scope: UserScope) -> int:
    total = 0
    for p in projects_qs(scope)[:LIMITE_LISTA]:
        total += count_diarios_aguardando_gestor(p)
    return total
