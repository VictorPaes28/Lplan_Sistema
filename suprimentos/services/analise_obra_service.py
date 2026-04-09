"""
Agregação para a página **Análise da Obra**: separa semanticamente três fontes:

- **controle** — `ItemMapaServico` (avanço físico / hierarquia da obra).
- **suprimentos** — `ItemMapa` via `MapaControleService` (pipeline SC/PC/entrega/alocação).
- **diario** — `ConstructionDiary` + `DiaryOccurrence` (fatos e ocorrências).

O bloco **cruzamento** apenas combina chaves compatíveis (ex.: nome de bloco/local),
sem somar indicadores heterogêneos num único número “mágico”.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from django.db.models import Count, Q

from django.utils import timezone

from core.models import ConstructionDiary, DiaryOccurrence, DiaryStatus, OccurrenceTag, Project
from mapa_obras.models import Obra
from suprimentos.models import ItemMapaServico
from suprimentos.services.mapa_controle_service import MapaControleFilters, MapaControleService


def _norm_key(value: object) -> str:
    text = (str(value or "")).strip().upper()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("ASCII")
    return " ".join(text.split())


def _status_to_ratio(item: ItemMapaServico) -> float | None:
    if item.status_percentual is not None:
        try:
            value = float(item.status_percentual)
        except (TypeError, ValueError):
            value = None
        if value is not None:
            if value > 1:
                value = value / 100.0
            return max(0.0, min(1.0, value))
    txt = (item.status_texto or "").strip().lower()
    if not txt:
        return None
    if "conclu" in txt or "final" in txt or "entreg" in txt or "feito" in txt or "ok" == txt:
        return 1.0
    if (
        "exec" in txt
        or "andamento" in txt
        or "andando" in txt
        or "parcial" in txt
        or "iniciad" in txt
        or "parado" in txt
    ):
        return 0.5
    if "nao" in txt or "não" in txt or "pend" in txt or "aguard" in txt or "bloq" in txt:
        return 0.0
    return None


def _resolve_project_for_obra(obra: Obra) -> Project | None:
    codes = {obra.codigo_sienge.strip()}
    raw = (obra.codigos_sienge_alternativos or "").strip()
    if raw:
        for part in re.split(r"[,;\n]+", raw):
            p = part.strip()
            if p:
                codes.add(p)
    for code in codes:
        p = Project.objects.filter(code=code).first()
        if p:
            return p
    return None


def _criticidade_from_pct(pct: float | None) -> str:
    if pct is None:
        return "sem_dado"
    if pct < 30:
        return "critica"
    if pct < 55:
        return "alta"
    if pct < 75:
        return "media"
    return "baixa"


def _classify_occurrence_severity(description: str, tag_names: list[str]) -> str:
    """
    Classifica severidade de ocorrência com heurística simples para leitura executiva.
    """
    tokens = " ".join([description or ""] + list(tag_names or [])).lower()
    if any(k in tokens for k in ("acidente", "embargo", "interdicao", "interdição", "colapso", "queda", "grave")):
        return "critica"
    if any(
        k in tokens
        for k in ("atraso", "parada", "bloqueio", "bloqueada", "falha", "erro", "seguranca", "segurança", "risco")
    ):
        return "alta"
    if any(k in tokens for k in ("pendencia", "pendência", "retrabalho", "ajuste", "nao conforme", "não conforme")):
        return "media"
    return "baixa"


@dataclass
class AnaliseObraPeriodo:
    data_inicio: date
    data_fim: date


@dataclass
class AnaliseObraFilters:
    """Filtros globais da análise (persistidos na querystring)."""

    setor: str = ""
    bloco: str = ""
    pavimento: str = ""
    apto: str = ""
    atividade: str = ""
    status_servico: str = ""  # concluido | em_andamento | nao_iniciado | ""
    local_suprimento_id: str = ""
    categoria_suprimento: str = ""
    prioridade_suprimento: str = ""
    status_suprimento: str = ""
    busca_suprimento: str = ""
    tag_ocorrencia_id: str = ""
    busca_diario_texto: str = ""
    responsavel_texto: str = ""
    visao: str = "geral"  # geral | detalhe

    def to_mapa_suprimentos_filters(self) -> MapaControleFilters:
        return MapaControleFilters(
            categoria=self.categoria_suprimento,
            local_id=self.local_suprimento_id,
            prioridade=self.prioridade_suprimento,
            status=self.status_suprimento,
            search=self.busca_suprimento,
            limit=500,
        )

    def to_dict(self) -> dict[str, str]:
        return {k: str(v) if v is not None else "" for k, v in asdict(self).items()}


class AnaliseObraService:
    def __init__(
        self,
        obra: Obra,
        periodo: AnaliseObraPeriodo | None = None,
        filtros: AnaliseObraFilters | None = None,
    ):
        self.obra = obra
        today = timezone.now().date()
        if periodo:
            self.periodo = periodo
        else:
            self.periodo = AnaliseObraPeriodo(data_inicio=today - timedelta(days=30), data_fim=today)
        self.filtros = filtros or AnaliseObraFilters()

    def controle_base_queryset(self):
        qs = ItemMapaServico.objects.filter(obra=self.obra)
        f = self.filtros
        if f.setor:
            qs = qs.filter(setor=f.setor)
        if f.bloco:
            qs = qs.filter(bloco=f.bloco)
        if f.pavimento:
            qs = qs.filter(pavimento=f.pavimento)
        if f.apto:
            qs = qs.filter(apto=f.apto)
        if f.atividade:
            qs = qs.filter(Q(atividade__icontains=f.atividade) | Q(grupo_servicos__icontains=f.atividade))
        if f.status_servico in {"concluido", "em_andamento", "nao_iniciado"}:
            # Filtra por status em Python para suportar fontes com percentual em 0-1 e 0-100.
            matched_ids: list[int] = []
            for item in qs.only("id", "status_percentual", "status_texto"):
                ratio = _status_to_ratio(item)
                if ratio is None:
                    continue
                if f.status_servico == "concluido" and ratio >= 0.999:
                    matched_ids.append(item.id)
                elif f.status_servico == "em_andamento" and 0.0 < ratio < 0.999:
                    matched_ids.append(item.id)
                elif f.status_servico == "nao_iniciado" and ratio <= 0.0:
                    matched_ids.append(item.id)
            qs = qs.filter(id__in=matched_ids) if matched_ids else qs.none()
        return qs

    def build_filtros_payload(self) -> dict[str, Any]:
        """Opções de dropdown e valores aplicados (para UI e API)."""
        base = ItemMapaServico.objects.filter(obra=self.obra)
        setores = list(base.exclude(setor="").values_list("setor", flat=True).distinct().order_by("setor")[:120])
        blocos = list(base.exclude(bloco="").values_list("bloco", flat=True).distinct().order_by("bloco")[:120])
        pavs = list(base.exclude(pavimento="").values_list("pavimento", flat=True).distinct().order_by("pavimento")[:80])
        aptos = list(base.exclude(apto="").values_list("apto", flat=True).distinct().order_by("apto")[:200])
        atividades = list(base.values_list("atividade", flat=True).distinct().order_by("atividade")[:200])

        mcf = MapaControleService(obra=self.obra, filters=MapaControleFilters(limit=1)).build_summary_payload()
        filt_sup = mcf.get("filtros") or {}

        tags = list(OccurrenceTag.objects.filter(is_active=True).order_by("name").values("id", "name", "color")[:200])

        return {
            "aplicados": self.filtros.to_dict(),
            "opcoes": {
                "setores": [{"id": s, "label": s} for s in setores],
                "blocos": [{"id": b, "label": b} for b in blocos],
                "pavimentos": [{"id": p, "label": p} for p in pavs],
                "aptos": [{"id": a, "label": a} for a in aptos],
                "atividades": [{"id": x, "label": x} for x in atividades if x],
                "status_servico": [
                    {"id": "", "label": "Todos"},
                    {"id": "concluido", "label": "Concluído"},
                    {"id": "em_andamento", "label": "Em andamento"},
                    {"id": "nao_iniciado", "label": "Não iniciado"},
                ],
                "visao": [
                    {"id": "geral", "label": "Visão geral"},
                    {"id": "detalhe", "label": "Visão detalhada"},
                ],
                "suprimentos": filt_sup.get("options") or {},
                "tags_ocorrencia": tags,
            },
        }

    def build_payload(self) -> dict[str, Any]:
        project = _resolve_project_for_obra(self.obra)
        controle = self._build_controle()
        suprimentos = self._build_suprimentos()
        diario = self._build_diario(project)
        cruzamento = self._build_cruzamento(controle, suprimentos, diario)
        heatmap = self._build_heatmap()
        situacao = self._classify_situacao(controle, suprimentos, diario)
        filtros = self.build_filtros_payload()

        return {
            "meta": {
                "obra_id": self.obra.id,
                "obra_nome": self.obra.nome,
                "obra_codigo": self.obra.codigo_sienge,
                "projeto_diario_codigo": project.code if project else None,
                "projeto_diario_nome": project.name if project else None,
                "periodo": {
                    "inicio": self.periodo.data_inicio.isoformat(),
                    "fim": self.periodo.data_fim.isoformat(),
                },
                "gerado_em": timezone.now().isoformat(),
                "situacao_executiva": situacao,
                "baseline_planejamento": {
                    "disponivel": False,
                    "mensagem": (
                        "Curva planejada × real depende da fonte de baseline definida pelo produto; "
                        "até lá o comparativo oficial de prazo não é exibido automaticamente."
                    ),
                },
            },
            "filtros": filtros,
            "controle": controle,
            "suprimentos": suprimentos,
            "diario": diario,
            "cruzamento": cruzamento,
            "heatmap": heatmap,
        }

    def build_section(self, secao: str) -> dict[str, Any] | None:
        """Retorna apenas um bloco do payload (para carregamento assíncrono por seção)."""
        full = self.build_payload()
        s = (secao or "").strip().lower()
        if s in ("", "all", "full"):
            return full
        if s in full:
            return {s: full[s]}
        return None

    def build_drill_down(self, bloco: str, pavimento: str) -> dict[str, Any]:
        """Detalhe para drawer: recorte do controle + resumo de suprimentos por busca no local."""
        bloco = (bloco or "").strip()
        pavimento = (pavimento or "").strip()
        qs = self.controle_base_queryset().filter(bloco=bloco)
        if pavimento:
            qs = qs.filter(pavimento=pavimento)

        itens = list(
            qs.order_by("apto", "atividade").values(
                "atividade",
                "apto",
                "pavimento",
                "status_texto",
                "status_percentual",
                "observacao",
            )[:80]
        )
        ratios = []
        for row in itens:
            sp = row.get("status_percentual")
            if sp is None:
                continue
            try:
                v = float(sp)
                if v > 1:
                    v = v / 100.0
                ratios.append(max(0.0, min(1.0, v)))
            except (TypeError, ValueError):
                continue
        pct_local = round((sum(ratios) / len(ratios)) * 100, 1) if ratios else None

        busca_local = f"{bloco} {pavimento}".strip()
        sup_filters = MapaControleFilters(
            categoria=self.filtros.categoria_suprimento,
            local_id=self.filtros.local_suprimento_id,
            prioridade=self.filtros.prioridade_suprimento,
            status=self.filtros.status_suprimento,
            search=busca_local or bloco,
            limit=200,
        )
        sup_res = MapaControleService(obra=self.obra, filters=sup_filters).build_summary_payload()

        return {
            "origem": "drilldown",
            "chave": {"bloco": bloco, "pavimento": pavimento},
            "controle": {
                "percentual_medio_local": pct_local,
                "total_linhas": len(itens),
                "linhas": itens,
            },
            "suprimentos": {
                "nota": "Resumo de suprimentos filtrado por termo de busca alinhado ao bloco/pavimento.",
                "kpis": sup_res.get("kpis"),
                "ranking_locais": (sup_res.get("ranking") or {}).get("locais")[:8],
            },
        }

    def _build_suprimentos(self) -> dict[str, Any]:
        raw = MapaControleService(obra=self.obra, filters=self.filtros.to_mapa_suprimentos_filters()).build_summary_payload()
        return {
            "origem": "mapa_suprimentos",
            "descricao_curta": "Pipeline de materiais: SC, PC, entrega, alocação e pendências.",
            "kpis": raw.get("kpis"),
            "ranking": raw.get("ranking"),
            "distribuicao_status": raw.get("distribuicao_status"),
            "obra": raw.get("obra"),
        }

    def _build_controle(self) -> dict[str, Any]:
        qs = self.controle_base_queryset()
        items = list(qs.only("status_percentual", "status_texto", "bloco", "pavimento", "atividade"))
        total = len(items)
        soma_pct = 0.0
        pct_count = 0
        concluidos = em_andamento = nao_iniciados = 0
        by_bloco: dict[str, list[float]] = {}

        for item in items:
            ratio = _status_to_ratio(item)
            bloco = _norm_key(item.bloco) or "SEM BLOCO"
            if ratio is not None:
                by_bloco.setdefault(bloco, []).append(ratio)
            if ratio is not None:
                soma_pct += ratio
                pct_count += 1
                if ratio >= 0.999:
                    concluidos += 1
                elif ratio <= 0.0:
                    nao_iniciados += 1
                else:
                    em_andamento += 1
            else:
                # Sem sinal confiável: mantém contagem conservadora em "não iniciado".
                nao_iniciados += 1

        pct_medio = round((soma_pct / pct_count) * 100, 2) if pct_count else 0.0

        bloco_scores = []
        for bloco, ratios in by_bloco.items():
            if not ratios:
                continue
            avg = sum(ratios) / len(ratios)
            bloco_scores.append({"bloco": bloco, "percentual_medio": round(avg * 100, 1), "amostras": len(ratios)})

        bloco_scores.sort(key=lambda x: x["percentual_medio"])
        piores = bloco_scores[:8]
        melhores = sorted(bloco_scores, key=lambda x: x["percentual_medio"], reverse=True)[:5]

        return {
            "origem": "mapa_controle_execucao",
            "descricao_curta": "Avanço físico por bloco, pavimento e atividade (importação do mapa de serviço).",
            "kpis": {
                "total_itens": total,
                "percentual_medio": pct_medio,
                "concluidos": concluidos,
                "em_andamento": em_andamento,
                "nao_iniciados": nao_iniciados,
            },
            "blocos_mais_atrasados": piores,
            "blocos_mais_avancados": melhores,
        }

    def _build_heatmap(self) -> dict[str, Any]:
        """Matriz bloco × pavimento com % médio e criticidade (somente controle)."""
        qs = self.controle_base_queryset()
        items = list(qs.only("bloco", "pavimento", "status_percentual", "status_texto"))
        agg: dict[tuple[str, str], list[float]] = {}
        for item in items:
            b = (item.bloco or "").strip() or "SEM BLOCO"
            p = (item.pavimento or "").strip() or "-"
            ratio = _status_to_ratio(item)
            if ratio is None:
                continue
            agg.setdefault((b, p), []).append(ratio)

        celulas = []
        for (b, p), ratios in agg.items():
            avg = sum(ratios) / len(ratios)
            pct = round(avg * 100, 1)
            celulas.append(
                {
                    "bloco": b,
                    "pavimento": p,
                    "percentual_medio": pct,
                    "amostras": len(ratios),
                    "criticidade": _criticidade_from_pct(pct),
                }
            )
        celulas.sort(key=lambda c: c["percentual_medio"])

        blocos = sorted({c["bloco"] for c in celulas})[:24]
        pavs = sorted({c["pavimento"] for c in celulas})[:18]

        return {
            "origem": "mapa_controle_execucao",
            "descricao_curta": "Criticidade consolidada apenas do avanço físico (não mistura suprimento nem diário).",
            "blocos_eixo": blocos,
            "pavimentos_eixo": pavs,
            "celulas": celulas[:400],
            "legenda_criticidade": {
                "critica": "< 30% executado",
                "alta": "30–55%",
                "media": "55–75%",
                "baixa": "≥ 75%",
                "sem_dado": "Sem amostra válida",
            },
        }

    def _build_diario(self, project: Project | None) -> dict[str, Any]:
        if not project:
            return {
                "origem": "diario_obra",
                "descricao_curta": "Registros diários e ocorrências de campo.",
                "vinculo_projeto": False,
                "mensagem": "Não há projeto do Diário com o mesmo código Sienge desta obra; cruzamentos com o diário ficam limitados.",
                "kpis": {},
                "ocorrencias_por_dia": [],
                "tags_top": [],
                "timeline": [],
                "prioridades": {"p1_critica": 0, "p2_alta": 0, "p3_media": 0, "p4_baixa": 0},
                "ocorrencias_recentes": [],
            }

        d1, d2 = self.periodo.data_inicio, self.periodo.data_fim
        diaries_qs = ConstructionDiary.objects.filter(project=project, date__gte=d1, date__lte=d2)
        f = self.filtros
        if f.responsavel_texto:
            rt = f.responsavel_texto.strip()
            diaries_qs = diaries_qs.filter(
                Q(inspection_responsible__icontains=rt) | Q(production_responsible__icontains=rt)
            )

        diarios_aprovados = diaries_qs.filter(status=DiaryStatus.APROVADO)
        total_diarios = diarios_aprovados.count()

        occ_qs = DiaryOccurrence.objects.filter(diary__in=diarios_aprovados)
        if f.tag_ocorrencia_id:
            try:
                tid = int(f.tag_ocorrencia_id)
                occ_qs = occ_qs.filter(tags__id=tid)
            except ValueError:
                pass
        if f.busca_diario_texto:
            occ_qs = occ_qs.filter(description__icontains=f.busca_diario_texto.strip())

        total_ocorrencias = occ_qs.count()

        por_dia = occ_qs.values("diary__date").annotate(n=Count("id")).order_by("diary__date")
        ocorrencias_por_dia = [{"data": row["diary__date"].isoformat(), "total": row["n"]} for row in por_dia]
        dias_com_ocorrencia = len(ocorrencias_por_dia)
        media_dia_com_evento = round((total_ocorrencias / dias_com_ocorrencia), 2) if dias_com_ocorrencia else 0.0
        dias_periodo = max(1, (d2 - d1).days + 1)
        taxa_dias_com_ocorrencia = round((dias_com_ocorrencia / dias_periodo) * 100.0, 1)

        tags_qs = (
            OccurrenceTag.objects.filter(occurrences__in=occ_qs)
            .annotate(n=Count("occurrences", filter=Q(occurrences__in=occ_qs), distinct=True))
            .order_by("-n", "name")[:12]
        )
        tags_top = [{"nome": t.name, "cor": t.color or "#64748b", "total": t.n} for t in tags_qs]

        priorities = {"p1_critica": 0, "p2_alta": 0, "p3_media": 0, "p4_baixa": 0}
        ocorrencias_recentes = []
        occ_recent_qs = (
            occ_qs.select_related("diary")
            .prefetch_related("tags")
            .order_by("-diary__date", "-created_at")
        )
        for occ in occ_recent_qs:
            tags_list = [t.name for t in occ.tags.all()]
            severity = _classify_occurrence_severity(occ.description or "", tags_list)
            if severity == "critica":
                priorities["p1_critica"] += 1
            elif severity == "alta":
                priorities["p2_alta"] += 1
            elif severity == "media":
                priorities["p3_media"] += 1
            else:
                priorities["p4_baixa"] += 1

            ocorrencias_recentes.append(
                {
                    "data": occ.diary.date.isoformat(),
                    "relatorio": occ.diary.report_number,
                    "descricao": (occ.description or "")[:220],
                    "gravidade": severity,
                    "tags": tags_list[:5],
                }
            )

        recent = diarios_aprovados.order_by("-date")[:12]
        timeline = []
        for d in recent:
            occ_n = d.occurrences.count()
            timeline.append(
                {
                    "data": d.date.isoformat(),
                    "relatorio": d.report_number,
                    "status": d.status,
                    "ocorrencias_no_dia": occ_n,
                    "resumo_clima": (d.weather_conditions or "")[:160],
                }
            )

        return {
            "origem": "diario_obra",
            "descricao_curta": "Fatos registrados no diário: ocorrências, tags e narrativa de campo.",
            "vinculo_projeto": True,
            "project_code": project.code,
            "kpis": {
                "diarios_aprovados_no_periodo": total_diarios,
                "ocorrencias_no_periodo": total_ocorrencias,
                "dias_com_ocorrencia": dias_com_ocorrencia,
                "media_por_dia_com_evento": media_dia_com_evento,
                "taxa_dias_com_ocorrencia": taxa_dias_com_ocorrencia,
                "ocorrencias_criticas_no_periodo": priorities["p1_critica"],
            },
            "ocorrencias_por_dia": ocorrencias_por_dia,
            "tags_top": tags_top,
            "timeline": timeline,
            "prioridades": priorities,
            "ocorrencias_recentes": ocorrencias_recentes,
        }

    def _build_cruzamento(
        self,
        controle: dict[str, Any],
        suprimentos: dict[str, Any],
        diario: dict[str, Any],
    ) -> dict[str, Any]:
        rank_locais = (suprimentos.get("ranking") or {}).get("locais") or []
        locais_sup = {_norm_key(name): int(n) for name, n in rank_locais if name}

        piores_blocos = {_norm_key(b.get("bloco")): b for b in (controle.get("blocos_mais_atrasados") or [])}

        candidatos = []
        max_pend = max(locais_sup.values()) if locais_sup else 0
        for bloco_key, ctrl in piores_blocos.items():
            if not bloco_key:
                continue
            pend_sup = locais_sup.get(bloco_key)
            if pend_sup is None:
                for lk, lv in locais_sup.items():
                    if bloco_key in lk or lk in bloco_key:
                        pend_sup = lv
                        break
            if pend_sup is not None:
                pct_ctrl = float(ctrl.get("percentual_medio") or 0)
                atraso_factor = max(0.0, (100.0 - pct_ctrl) / 100.0)
                pend_factor = (pend_sup / max_pend) if max_pend else 0.0
                risco = round((atraso_factor * 0.6 + pend_factor * 0.4) * 100.0, 1)
                if risco >= 70:
                    prioridade = "urgente"
                elif risco >= 50:
                    prioridade = "alta"
                elif risco >= 30:
                    prioridade = "media"
                else:
                    prioridade = "baixa"
                candidatos.append(
                    {
                        "local_norm": bloco_key,
                        "leitura": (
                            "Avanço físico abaixo do esperado e pendência relevante de material no mesmo eixo."
                        ),
                        "controle": {
                            "percentual_medio": ctrl.get("percentual_medio"),
                            "amostras": ctrl.get("amostras"),
                        },
                        "suprimentos": {"pendencias_pendentes_ranking": pend_sup},
                        "prioridade": prioridade,
                        "score_risco": risco,
                        "diario": {"nota": "Detalhar ocorrências no diário filtrando período e local equivalente."},
                    }
                )

        candidatos.sort(key=lambda x: x.get("score_risco", 0), reverse=True)

        prioridades_diario = (diario.get("prioridades") or {}) if isinstance(diario, dict) else {}
        p1 = int(prioridades_diario.get("p1_critica") or 0)
        p2 = int(prioridades_diario.get("p2_alta") or 0)

        acoes_recomendadas: list[dict[str, str]] = []
        if candidatos:
            top = candidatos[0]
            top_local = top.get("local_norm") or "local crítico"
            top_pri = (top.get("prioridade") or "alta").upper()
            acoes_recomendadas.append(
                {
                    "prioridade": top_pri,
                    "acao": f"Alinhar obra e suprimentos no {top_local} e remover bloqueio de material no mesmo turno.",
                }
            )
        if p1 > 0:
            acoes_recomendadas.append(
                {
                    "prioridade": "URGENTE",
                    "acao": "Revisar ocorrências críticas de campo ainda hoje com responsável da obra e registrar plano de contenção.",
                }
            )
        if p2 > 0:
            acoes_recomendadas.append(
                {
                    "prioridade": "ALTA",
                    "acao": "Priorizar pendências de suprimentos com impacto direto na execução para evitar paralisação.",
                }
            )
        if not acoes_recomendadas:
            acoes_recomendadas.append(
                {
                    "prioridade": "ROTINA",
                    "acao": "Manter monitoramento diário e revisar novamente após atualização dos filtros.",
                }
            )

        return {
            "origem": "cruzamento",
            "descricao_curta": "Hipóteses de causa: combina sinais sem misturar definições.",
            "candidatos_atraso_suprimento_e_execucao": candidatos[:10],
            "acoes_recomendadas": acoes_recomendadas[:3],
            "alertas_semanticos": [
                "Ocorrência do diário ≠ pendência de suprimento ≠ percentual de serviço; cada card indica a origem.",
                "Indicadores de suprimento medem abastecimento; percentual de serviço mede execução física.",
            ],
        }

    def _classify_situacao(self, controle: dict, suprimentos: dict, diario: dict) -> dict[str, Any]:
        kc = controle.get("kpis") or {}
        ks = suprimentos.get("kpis") or {}
        kd = diario.get("kpis") or {}
        pr = diario.get("prioridades") or {}

        pct = float(kc.get("percentual_medio") or 0)
        atrasados = int(ks.get("atrasados") or 0)
        occ = int(kd.get("ocorrencias_no_periodo") or 0)
        occ_crit = int(pr.get("p1_critica") or kd.get("ocorrencias_criticas_no_periodo") or 0)

        sinais = 0
        motivos = []
        if pct < 35:
            sinais += 2
            motivos.append("Execução física baixa no recorte.")
        elif pct < 55:
            sinais += 1
            motivos.append("Execução física em atenção.")

        if atrasados >= 15:
            sinais += 2
            motivos.append("Fila de suprimentos com muitos atrasos.")
        elif atrasados >= 6:
            sinais += 1
            motivos.append("Fila de suprimentos sob pressão.")

        if occ_crit >= 3:
            sinais += 2
            motivos.append("Ocorrências críticas recorrentes no diário.")
        elif occ_crit >= 1:
            sinais += 1
            motivos.append("Há ocorrência crítica no período.")
        elif occ >= 12:
            sinais += 1
            motivos.append("Volume de ocorrências acima do normal.")

        if sinais <= 1:
            rotulo = "Obra dentro do previsto"
            nivel = "ok"
        elif sinais <= 3:
            rotulo = "Obra em atenção"
            nivel = "atencao"
        else:
            rotulo = "Obra com risco de atraso ou pressão operacional"
            nivel = "risco"

        return {"rotulo": rotulo, "nivel": nivel, "motivos": motivos}
