"""Portfólio multi-obra do BI — ranking, alertas e resumo operacional por obra."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any

from django.db.models import OuterRef, Subquery
from django.urls import reverse
from django.utils import timezone

from core.models import Project
from mapa_obras.models import Obra
from painel_operacional.models import AmbienteOperacional, AmbienteTipo
from suprimentos.models import BiObraKpiSnapshot


def _classify_portfolio_row(
    *,
    avanco: float | None,
    restricoes: int,
    pendentes: int,
    rdos: int,
    sup_atrasados: int,
    tem_mapa: bool,
    situacao_exec: dict[str, Any] | None = None,
) -> tuple[str, str, list[str]]:
    """Retorna (codigo, rótulo, motivos curtos)."""
    if situacao_exec and situacao_exec.get("motivos"):
        nivel = situacao_exec.get("nivel") or "atencao"
        label_map = {"ok": "Normal", "atencao": "Atenção", "risco": "Crítica"}
        codigo_map = {"ok": "normal", "atencao": "atencao", "risco": "critica"}
        motivos = list(situacao_exec.get("motivos") or [])[:4]
        if not tem_mapa and "Sem mapa" not in " ".join(motivos):
            motivos.append("Sem mapa de controle")
        return (
            codigo_map.get(nivel, "atencao"),
            label_map.get(nivel, "Atenção"),
            motivos[:4],
        )

    motivos: list[str] = []
    score = 0

    if restricoes > 0:
        score += 2 if restricoes >= 3 else 1
        motivos.append(f"{restricoes} restrição(ões) aberta(s)")
    if sup_atrasados >= 6:
        score += 2
        motivos.append(f"{sup_atrasados} suprimentos atrasados")
    elif sup_atrasados > 0:
        score += 1
        motivos.append(f"{sup_atrasados} suprimento(s) atrasado(s)")
    if pendentes >= 3:
        score += 1
        motivos.append(f"{pendentes} pedido(s) pendentes")
    if rdos >= 2:
        score += 1
        motivos.append(f"{rdos} RDO(s) pendente(s)")
    if avanco is not None and avanco < 30:
        score += 2
        motivos.append(f"Avanço físico baixo ({avanco:.0f}%)")
    elif avanco is not None and avanco < 45:
        score += 1
        motivos.append(f"Avanço físico moderado ({avanco:.0f}%)")
    if not tem_mapa:
        motivos.append("Sem mapa de controle")

    if score >= 3:
        return "critica", "Crítica", motivos[:4]
    if score >= 1:
        return "atencao", "Atenção", motivos[:4]
    if avanco is None and not motivos:
        return "sem_dado", "Sem dado", ["Snapshot ou mapa ainda não disponível"]
    return "normal", "Normal", motivos[:2]


def _sparkline_from_snaps(
    snaps: list[BiObraKpiSnapshot],
    dias: list,
    attr: str,
) -> list[float | None]:
    by_date = {s.data: s for s in snaps}
    out: list[float | None] = []
    for d in dias:
        snap = by_date.get(d)
        if not snap:
            out.append(None)
            continue
        val = getattr(snap, attr, None)
        out.append(float(val) if val is not None else None)
    return out


def _delta_7d(series: list[float | None]) -> float | None:
    vals = [v for v in series if v is not None]
    if len(vals) < 2:
        return None
    return round(vals[-1] - vals[0], 1)


def _load_modulos_obra(
    obra: Obra,
    *,
    periodo: "AnaliseObraPeriodo",
) -> dict[str, Any]:
    """Carrega controle, suprimentos, TrackHub e síntese executiva para uma obra."""
    from suprimentos.services.analise_obra_service import (
        AnaliseObraPeriodo,
        AnaliseObraService,
        _resolve_project_for_obra,
    )

    svc = AnaliseObraService(obra, periodo=periodo)
    project = _resolve_project_for_obra(obra)

    controle = svc._build_controle(include_progressao_completo=False)
    suprimentos = svc._build_suprimentos(include_extras=False)
    diario = svc._build_diario(project, extended=False)
    gestcontroll = svc._build_gestcontroll()
    restricoes = svc._build_restricoes()
    trackhub = svc._build_trackhub()
    cruzamento = svc._build_cruzamento(controle, suprimentos, diario)
    situacao = svc._classify_situacao(controle, suprimentos, diario)
    acoes = svc._build_acoes_prioritarias(
        controle, suprimentos, diario, gestcontroll, restricoes
    )
    go = svc._gestao_obra

    ck = controle.get("kpis") or {}
    sk = suprimentos.get("kpis") or {}
    piores = controle.get("blocos_mais_atrasados") or controle.get("progresso_blocos") or []
    atividades = controle.get("atividades_mais_criticas") or []

    return {
        "gestao_obra_id": go.id if go else None,
        "situacao_executiva": situacao,
        "acoes": acoes[:5],
        "cruzamento": cruzamento,
        "rdos_pendentes": int(
            (diario.get("rdos_resumo") or {}).get("pendentes_rdos_count") or 0
        ),
        "execucao": {
            "sem_dados": bool(controle.get("sem_dados")),
            "concluidos": int(ck.get("concluidos") or 0),
            "em_andamento": int(ck.get("em_andamento") or 0),
            "nao_iniciados": int(ck.get("nao_iniciados") or 0),
            "total_unidades": int(ck.get("total_itens") or 0),
            "piores_blocos": [
                {
                    "rotulo": (b.get("rotulo") or b.get("bloco") or b.get("nome") or "—"),
                    "bloco": (b.get("bloco") or "").strip(),
                    "setor": (b.get("setor") or "").strip(),
                    "pct": b.get("percentual_medio"),
                }
                for b in piores[:3]
                if b.get("percentual_medio") is not None
            ],
            "atividades_criticas": [
                {
                    "nome": (a.get("atividade") or a.get("nome") or "—"),
                    "pct": a.get("percentual_medio") or a.get("percentual"),
                }
                for a in atividades[:3]
                if (a.get("percentual_medio") or a.get("percentual")) is not None
            ],
            "ambiente_id": controle.get("ambiente_id"),
        },
        "suprimentos": {
            "total": int(sk.get("total_itens") or 0),
            "atrasados": int(sk.get("atrasados") or 0),
            "sem_alocacao": int(sk.get("levantamento") or 0),
            "parciais": int(sk.get("parciais") or 0),
            "entregues": int(sk.get("entregues") or 0),
        },
        "diario": {
            "ocorrencias_periodo": int((diario.get("kpis") or {}).get("ocorrencias_no_periodo") or 0),
            "ocorrencias_criticas": int(
                (diario.get("prioridades") or {}).get("p1_critica")
                or (diario.get("kpis") or {}).get("ocorrencias_criticas_no_periodo")
                or 0
            ),
        },
        "gestcontroll": {
            "pendentes": int((gestcontroll.get("kpis") or {}).get("pendentes_count") or 0),
            "valor_aprovacao": float((gestcontroll.get("kpis") or {}).get("pendentes_valor") or 0),
        },
        "restricoes": {
            "abertas": int((restricoes.get("kpis") or {}).get("total_aberto") or 0),
            "vencidas": int((restricoes.get("kpis") or {}).get("vencidas") or 0),
        },
        "trackhub": {
            "abertas": int((trackhub.get("resumo") or {}).get("total_aberto") or 0),
            "vencidas": int((trackhub.get("resumo") or {}).get("vencidas") or 0),
            "em_andamento": int((trackhub.get("resumo") or {}).get("em_andamento") or 0),
            "mais_atrasadas": (trackhub.get("mais_atrasadas") or [])[:3],
        },
    }


class AnaliseObraPortfolioService:
    """Monta visão consolidada das obras acessíveis ao usuário."""

    def __init__(
        self,
        obras_qs,
        *,
        somente_alerta: bool = False,
        periodo=None,
        periodo_preset: str = "30",
    ):
        from suprimentos.services.analise_obra_service import AnaliseObraPeriodo

        self.obras_qs = obras_qs.filter(ativa=True).select_related("project")
        self.somente_alerta = somente_alerta
        hoje = timezone.localdate()
        self.periodo = periodo or AnaliseObraPeriodo(
            data_inicio=hoje - timedelta(days=30),
            data_fim=hoje,
        )
        self.periodo_preset = periodo_preset or "30"

    def build(self) -> dict[str, Any]:
        obras = list(self.obras_qs.order_by("nome"))
        obra_ids = [o.id for o in obras]
        if not obra_ids:
            return self._empty_payload()

        hoje = timezone.localdate()
        dias_spark = [hoje - timedelta(days=i) for i in range(6, -1, -1)]

        latest_sq = BiObraKpiSnapshot.objects.filter(obra_id=OuterRef("pk")).order_by("-data")
        project_sq = Project.objects.filter(pk=OuterRef("project_id"))

        obras_ann = (
            Obra.objects.filter(id__in=obra_ids)
            .annotate(
                snap_avanco=Subquery(latest_sq.values("avanco_fisico_pct")[:1]),
                snap_restricoes=Subquery(latest_sq.values("restricoes_abertas")[:1]),
                snap_pendentes=Subquery(latest_sq.values("pendentes_gestcontroll")[:1]),
                snap_rdos=Subquery(latest_sq.values("rdos_pendentes")[:1]),
                snap_data=Subquery(latest_sq.values("data")[:1]),
                projeto_cliente=Subquery(project_sq.values("client_name")[:1]),
                projeto_responsavel=Subquery(project_sq.values("responsible")[:1]),
            )
        )
        ann_by_id = {o.id: o for o in obras_ann}

        ambientes = {
            a.obra_id: a.id
            for a in AmbienteOperacional.objects.filter(
                obra_id__in=obra_ids,
                tipo=AmbienteTipo.MAPA_CONTROLE,
                ativo=True,
            ).order_by("-updated_at")
        }

        snaps_7d = BiObraKpiSnapshot.objects.filter(
            obra_id__in=obra_ids,
            data__gte=dias_spark[0],
        ).order_by("obra_id", "data")
        snaps_by_obra: dict[int, list[BiObraKpiSnapshot]] = defaultdict(list)
        for snap in snaps_7d:
            snaps_by_obra[snap.obra_id].append(snap)

        sup_stats_map = self._batch_suprimentos_stats(obra_ids)

        from suprimentos.services.analise_obra_portfolio_links import (
            build_gargalos_e_resolver,
            mapa_controle_filtro_url,
            merge_fila_global,
            portfolio_obra_links,
        )

        rows: list[dict[str, Any]] = []
        for obra in obras:
            ann = ann_by_id.get(obra.id)
            avanco_raw = getattr(ann, "snap_avanco", None) if ann else None
            avanco = float(avanco_raw) if avanco_raw is not None else None
            restricoes = int(getattr(ann, "snap_restricoes", None) or 0) if ann else 0
            pendentes = int(getattr(ann, "snap_pendentes", None) or 0) if ann else 0
            rdos = int(getattr(ann, "snap_rdos", None) or 0) if ann else 0
            snap_data = getattr(ann, "snap_data", None) if ann else None
            cliente = (getattr(ann, "projeto_cliente", None) or "").strip() if ann else ""
            responsavel = (getattr(ann, "projeto_responsavel", None) or "").strip() if ann else ""
            tem_mapa = obra.id in ambientes
            obra_snaps = snaps_by_obra.get(obra.id, [])

            spark_avanco = _sparkline_from_snaps(obra_snaps, dias_spark, "avanco_fisico_pct")
            spark_restr = _sparkline_from_snaps(obra_snaps, dias_spark, "restricoes_abertas")
            ocorrencias_7d = sum(int(s.ocorrencias_dia or 0) for s in obra_snaps)

            modulos = _load_modulos_obra(obra, periodo=self.periodo)
            sup = modulos["suprimentos"]
            if sup["total"] == 0 and sup_stats_map.get(obra.id):
                sup = {**sup, **sup_stats_map[obra.id]}

            restr_mod = dict(modulos["restricoes"])
            if restricoes > int(restr_mod.get("abertas") or 0):
                restr_mod["abertas"] = restricoes
            gest_mod = dict(modulos["gestcontroll"])
            if pendentes > int(gest_mod.get("pendentes") or 0):
                gest_mod["pendentes"] = pendentes
            rdos_mod = max(int(modulos.get("rdos_pendentes") or 0), rdos)

            execucao = modulos["execucao"]
            ambiente_id = execucao.get("ambiente_id") or ambientes.get(obra.id)
            gestao_obra_id = modulos.get("gestao_obra_id")
            situacao_exec = modulos.get("situacao_executiva")

            links = portfolio_obra_links(
                obra.id,
                gestao_obra_id=gestao_obra_id,
                ambiente_id=ambiente_id,
                periodo_preset=self.periodo_preset,
            )
            modulos_resolver = {
                **modulos,
                "restricoes": restr_mod,
                "gestcontroll": gest_mod,
                "rdos_pendentes": rdos_mod,
                "suprimentos": sup,
                "trackhub": modulos.get("trackhub") or {},
            }
            gargalos, resolver, gargalo_principal = build_gargalos_e_resolver(
                obra.id,
                obra.nome,
                modulos_resolver,
                links,
                gestao_obra_id=gestao_obra_id,
                ambiente_id=ambiente_id,
            )
            execucao = dict(execucao)
            execucao["piores_blocos"] = [
                {
                    **b,
                    "url": mapa_controle_filtro_url(
                        obra.id,
                        ambiente_id,
                        bloco=(b.get("bloco") or b.get("rotulo") or "").split("·")[-1].strip(),
                        setor=b.get("setor") or "",
                    ),
                }
                for b in execucao.get("piores_blocos") or []
            ]

            situacao, situacao_label, motivos = _classify_portfolio_row(
                avanco=avanco,
                restricoes=restricoes,
                pendentes=pendentes,
                rdos=rdos,
                sup_atrasados=sup.get("atrasados", 0),
                tem_mapa=tem_mapa,
                situacao_exec=situacao_exec,
            )

            if self.somente_alerta and situacao == "normal" and not resolver:
                continue

            rows.append(
                {
                    "obra_id": obra.id,
                    "codigo": obra.codigo_sienge or "",
                    "nome": obra.nome,
                    "cliente": cliente,
                    "responsavel": responsavel,
                    "tem_mapa_controle": tem_mapa,
                    "situacao": situacao,
                    "situacao_label": situacao_label,
                    "motivos": motivos,
                    "situacao_executiva": situacao_exec,
                    "avanco_fisico_pct": avanco,
                    "avanco_delta_7d": _delta_7d(spark_avanco),
                    "restricoes_abertas": restricoes,
                    "restricoes_vencidas": modulos["restricoes"]["vencidas"],
                    "pendentes_gestcontroll": pendentes,
                    "valor_em_aprovacao": modulos["gestcontroll"]["valor_aprovacao"],
                    "rdos_pendentes": rdos_mod,
                    "suprimentos": sup,
                    "execucao": execucao,
                    "diario": {
                        **modulos["diario"],
                        "ocorrencias_7d": ocorrencias_7d,
                    },
                    "trackhub": modulos.get("trackhub") or {},
                    "links": links,
                    "gargalos": gargalos,
                    "gargalo_principal": gargalo_principal,
                    "resolver": resolver,
                    "sparkline_avanco": spark_avanco,
                    "sparkline_restricoes": spark_restr,
                    "snapshot_data": snap_data.isoformat() if snap_data else None,
                    "ambiente_id": ambiente_id,
                    "gestao_obra_id": gestao_obra_id,
                    "bi_url": links["bi"],
                    "mapa_url": links.get("mapa_controle") or links["mapa"],
                }
            )

        rows.sort(
            key=lambda r: (
                {"critica": 0, "atencao": 1, "sem_dado": 2, "normal": 3}.get(r["situacao"], 9),
                r["avanco_fisico_pct"] is None,
                r["avanco_fisico_pct"] if r["avanco_fisico_pct"] is not None else 999,
                r["nome"].casefold(),
            )
        )

        avancos = [r["avanco_fisico_pct"] for r in rows if r["avanco_fisico_pct"] is not None]
        media_avanco = round(sum(avancos) / len(avancos), 1) if avancos else None

        totais = {
            "restricoes_abertas": sum(r["restricoes_abertas"] for r in rows),
            "restricoes_vencidas": sum(r["restricoes_vencidas"] for r in rows),
            "pendentes_gestcontroll": sum(r["pendentes_gestcontroll"] for r in rows),
            "rdos_pendentes": sum(r["rdos_pendentes"] for r in rows),
            "suprimentos_atrasados": sum(r["suprimentos"]["atrasados"] for r in rows),
            "suprimentos_total": sum(r["suprimentos"]["total"] for r in rows),
            "ocorrencias_7d": sum(r["diario"]["ocorrencias_7d"] for r in rows),
            "trackhub_abertas": sum(int((r.get("trackhub") or {}).get("abertas") or 0) for r in rows),
            "trackhub_vencidas": sum(int((r.get("trackhub") or {}).get("vencidas") or 0) for r in rows),
        }
        obras_alerta = sum(1 for r in rows if r["situacao"] in ("critica", "atencao"))
        fila_resolver = merge_fila_global(rows)

        return {
            "gerado_em": timezone.now().isoformat(),
            "resumo": {
                "total_obras": len(rows),
                "obras_alerta": obras_alerta,
                "obras_criticas": sum(1 for r in rows if r["situacao"] == "critica"),
                "obras_sem_mapa": sum(1 for r in rows if not r["tem_mapa_controle"]),
                "media_avanco_fisico": media_avanco,
                "itens_resolver": len(fila_resolver),
                "totais": totais,
            },
            "fila_resolver": fila_resolver,
            "obras": rows,
            "periodo": {
                "inicio": self.periodo.data_inicio.isoformat(),
                "fim": self.periodo.data_fim.isoformat(),
                "dias": (self.periodo.data_fim - self.periodo.data_inicio).days,
                "preset": self.periodo_preset,
            },
            "filtros": {
                "somente_alerta": self.somente_alerta,
                "periodo": self.periodo_preset,
            },
        }

    @staticmethod
    def _batch_suprimentos_stats(obra_ids: list[int]) -> dict[int, dict[str, int]]:
        from suprimentos.views_engenharia import _mapa_stats_agregados_manual

        if not obra_ids:
            return {}
        out: dict[int, dict[str, int]] = {}
        for oid in obra_ids:
            kpis = (_mapa_stats_agregados_manual(oid).get("kpis") or {})
            out[oid] = {
                "total": int(kpis.get("total") or 0),
                "atrasados": int(kpis.get("atrasados") or 0),
                "sem_alocacao": int(kpis.get("levantamento") or 0),
                "parciais": int(kpis.get("parciais") or 0),
                "entregues": int(kpis.get("entregues") or 0),
            }
        return out

    @staticmethod
    def _empty_payload() -> dict[str, Any]:
        return {
            "gerado_em": timezone.now().isoformat(),
            "resumo": {
                "total_obras": 0,
                "obras_alerta": 0,
                "obras_criticas": 0,
                "obras_sem_mapa": 0,
                "media_avanco_fisico": None,
                "itens_resolver": 0,
                "totais": {
                    "restricoes_abertas": 0,
                    "restricoes_vencidas": 0,
                    "pendentes_gestcontroll": 0,
                    "rdos_pendentes": 0,
                    "suprimentos_atrasados": 0,
                    "suprimentos_total": 0,
                    "ocorrencias_7d": 0,
                    "trackhub_abertas": 0,
                    "trackhub_vencidas": 0,
                },
            },
            "obras": [],
            "fila_resolver": [],
            "periodo": {
                "inicio": None,
                "fim": None,
                "dias": 0,
                "preset": "30",
            },
            "filtros": {"somente_alerta": False, "periodo": "30"},
        }
