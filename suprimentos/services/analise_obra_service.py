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
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from django.db.models import Count, Prefetch, Q

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


def _representative_bloco_label(bloco_norm: str, votes: Counter[str]) -> str:
    """
    Rótulo para exibição e parâmetro `bloco=` no Mapa de Controle: valor mais frequente
    no banco (match exato no ORM). `bloco_norm` é a chave de agrupamento (_norm_key).
    """
    if votes:
        return votes.most_common(1)[0][0]
    if bloco_norm == "SEM BLOCO":
        return "SEM BLOCO"
    return bloco_norm


EIXO_SETOR_BLOCO_SEP = "\x1f"


def _pair_votes_to_bloco_counter(votes: Counter[tuple[str, str]]) -> Counter[str]:
    c: Counter[str] = Counter()
    for (_rs, rb), n in votes.items():
        if rb:
            c[rb] += n
    return c


def _quota_setor_key(row: dict[str, Any]) -> str:
    """Chave estável para limitar quantas linhas por setor no ranking."""
    sn = (row.get("setor_norm") or "").strip()
    if sn:
        return sn
    raw = (row.get("setor") or "").strip()
    if raw:
        return _norm_key(raw)
    return "SEM SETOR"


def _progressao_eixo_sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
    """Ordem alfabética estável: setor, bloco (chave norm), rótulo."""
    s = (row.get("setor_norm") or "").casefold()
    b = (row.get("bloco_norm") or "").casefold()
    r = (row.get("rotulo") or "").casefold()
    return (s, b, r)


def _diversificar_ranking_por_setor(
    bloco_scores: list[dict[str, Any]],
    *,
    use_setor_grupo: bool,
    max_total: int,
    max_por_setor: int,
    piores: bool,
) -> list[dict[str, Any]]:
    """
    Com vários setores, evita que um único (ex.: ÁREA COMUM) monopolize o gráfico:
    percorre o ranking global (piores = % crescente, melhores = % decrescente) e só aceita
    uma linha se ainda não atingiu o teto por setor.
    """
    if not bloco_scores:
        return []
    rev = not piores
    ordenados = sorted(bloco_scores, key=lambda x: x["percentual_medio"], reverse=rev)
    if not use_setor_grupo:
        return ordenados[:max_total]

    counts: dict[str, int] = defaultdict(int)
    out: list[dict[str, Any]] = []
    for row in ordenados:
        k = _quota_setor_key(row)
        if counts[k] >= max_por_setor:
            continue
        out.append(row)
        counts[k] += 1
        if len(out) >= max_total:
            break
    out.sort(key=lambda x: x["percentual_medio"], reverse=not piores)
    return out


def _representative_setor_bloco_from_votes(
    votes: Counter[tuple[str, str]],
    setor_key: str,
    bloco_key: str,
) -> tuple[str, str, str]:
    """
    A partir de votos (setor_raw, bloco_raw), devolve (rótulo UI, setor_raw, bloco_raw)
    para links ?setor=&bloco= com strings existentes no banco.
    """
    if votes:
        (rs, rb), _ = votes.most_common(1)[0]
        parts = [p for p in [rs, rb] if p]
        rotulo = " · ".join(parts) if parts else (bloco_key if bloco_key != "SEM BLOCO" else "SEM BLOCO")
        return rotulo, rs or "", rb or ""
    if setor_key and setor_key != "SEM SETOR":
        rotulo = f"{setor_key} · {bloco_key}"
        return rotulo, "", ""
    rotulo = bloco_key if bloco_key != "SEM BLOCO" else "SEM BLOCO"
    return rotulo, "", ""


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
        dias_periodo = max(1, (self.periodo.data_fim - self.periodo.data_inicio).days + 1)
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
                    "dias": dias_periodo,
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

    def build_drill_down(self, bloco: str, pavimento: str, setor: str | None = None) -> dict[str, Any]:
        """Detalhe para drawer: recorte do controle + resumo de suprimentos por busca no local."""
        bloco = (bloco or "").strip()
        pavimento = (pavimento or "").strip()
        setor = (setor or "").strip()
        qs = self.controle_base_queryset().filter(bloco=bloco)
        if setor:
            qs = qs.filter(setor=setor)
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
        def _row_ratio(row: dict[str, Any]) -> float | None:
            sp = row.get("status_percentual")
            if sp is not None:
                try:
                    v = float(sp)
                    if v > 1:
                        v = v / 100.0
                    return max(0.0, min(1.0, v))
                except (TypeError, ValueError):
                    pass
            st = (row.get("status_texto") or "").strip().lower()
            if not st:
                return None
            if "conclu" in st or "final" in st or "entreg" in st or "feito" in st:
                return 1.0
            if "exec" in st or "andamento" in st or "andando" in st or "parcial" in st or "parado" in st:
                return 0.5
            if "nao" in st or "não" in st or "pend" in st or "aguard" in st or "bloq" in st:
                return 0.0
            return None

        ratios = []
        concluidos = em_andamento = nao_iniciados = sem_dado = 0
        itens_com_ratio = []
        for row in itens:
            ratio = _row_ratio(row)
            if ratio is None:
                sem_dado += 1
                continue
            ratios.append(ratio)
            itens_com_ratio.append((row, ratio))
            if ratio >= 0.999:
                concluidos += 1
            elif ratio <= 0.0:
                nao_iniciados += 1
            else:
                em_andamento += 1
        pct_local = round((sum(ratios) / len(ratios)) * 100, 1) if ratios else None
        itens_com_ratio.sort(key=lambda x: x[1])
        atividades_criticas = [
            {
                "atividade": row.get("atividade"),
                "apto": row.get("apto"),
                "status_texto": row.get("status_texto"),
                "percentual": round(ratio * 100, 1),
            }
            for row, ratio in itens_com_ratio[:5]
        ]
        linhas_preview = itens[:12]

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
        sup_kpis = sup_res.get("kpis") or {}
        ranking_locais = (sup_res.get("ranking") or {}).get("locais")[:8]
        materiais_criticos = [{"local": x[0], "pendencias": x[1]} for x in ranking_locais[:5]]

        atrasados = int(sup_kpis.get("atrasados") or 0)
        score_exec = max(0.0, 100.0 - float(pct_local or 0.0))
        score_sup = min(100.0, float(atrasados) * 6.0)
        score = round(score_exec * 0.6 + score_sup * 0.4, 1)
        if score >= 70:
            prioridade = "urgente"
            acao = "Atuar hoje no local: destravar material e alinhar frente com encarregado."
        elif score >= 50:
            prioridade = "alta"
            acao = "Planejar ação no próximo turno com foco nas pendências de material."
        elif score >= 30:
            prioridade = "media"
            acao = "Monitorar evolução diária e revisar novos bloqueios."
        else:
            prioridade = "baixa"
            acao = "Manter acompanhamento de rotina."

        return {
            "origem": "drilldown",
            "chave": {"bloco": bloco, "pavimento": pavimento},
            "controle": {
                "percentual_medio_local": pct_local,
                "total_linhas": len(itens),
                "linhas": itens,
                "linhas_preview": linhas_preview,
                "resumo_status": {
                    "concluidos": concluidos,
                    "em_andamento": em_andamento,
                    "nao_iniciados": nao_iniciados,
                    "sem_dado": sem_dado,
                },
                "atividades_criticas": atividades_criticas,
            },
            "suprimentos": {
                "nota": "Resumo de suprimentos filtrado por termo de busca alinhado ao bloco/pavimento.",
                "kpis": sup_kpis,
                "ranking_locais": ranking_locais,
                "materiais_criticos": materiais_criticos,
            },
            "resumo_executivo": {"prioridade": prioridade, "score": score, "acao": acao},
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
        items = list(
            qs.only("status_percentual", "status_texto", "setor", "bloco", "pavimento", "atividade")
        )
        total = len(items)
        soma_pct = 0.0
        pct_count = 0
        concluidos = em_andamento = nao_iniciados = 0

        setores_ns = {_norm_key(it.setor) for it in items if (str(it.setor or "")).strip()}
        use_setor_grupo = len(setores_ns) >= 2

        by_eixo: dict[str, list[float]] = {}
        pair_votes: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)

        for item in items:
            ratio = _status_to_ratio(item)
            sn = _norm_key(item.setor)
            bn = _norm_key(item.bloco) or "SEM BLOCO"
            raw_s = (str(item.setor or "")).strip()
            raw_b = (str(item.bloco or "")).strip()

            if use_setor_grupo:
                sn_g = sn if sn else "SEM SETOR"
                gkey = f"{sn_g}{EIXO_SETOR_BLOCO_SEP}{bn}"
            else:
                gkey = bn

            if ratio is not None:
                by_eixo.setdefault(gkey, []).append(ratio)
                if use_setor_grupo:
                    if raw_s or raw_b:
                        pair_votes[gkey][(raw_s, raw_b)] += 1
                elif raw_b:
                    pair_votes[gkey][("", raw_b)] += 1
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
        for gkey, ratios in by_eixo.items():
            if not ratios:
                continue
            avg = sum(ratios) / len(ratios)
            if use_setor_grupo:
                sk, bk = gkey.split(EIXO_SETOR_BLOCO_SEP, 1)
            else:
                sk, bk = "", gkey

            votes = pair_votes.get(gkey, Counter())
            rotulo, rs, rb = _representative_setor_bloco_from_votes(votes, sk, bk)
            if not rb:
                rb = _representative_bloco_label(bk, _pair_votes_to_bloco_counter(votes))

            setor_norm_out = ""
            if use_setor_grupo and sk and sk != "SEM SETOR":
                setor_norm_out = sk

            row = {
                "rotulo": rotulo,
                "setor": rs,
                "bloco": rb,
                "setor_norm": setor_norm_out,
                "bloco_norm": bk,
                "percentual_medio": round(avg * 100, 1),
                "amostras": len(ratios),
            }
            bloco_scores.append(row)

        piores = _diversificar_ranking_por_setor(
            bloco_scores,
            use_setor_grupo=use_setor_grupo,
            max_total=16,
            max_por_setor=3,
            piores=True,
        )
        melhores = _diversificar_ranking_por_setor(
            bloco_scores,
            use_setor_grupo=use_setor_grupo,
            max_total=10,
            max_por_setor=2,
            piores=False,
        )

        ordenado_pior_melhor = sorted(bloco_scores, key=lambda x: x["percentual_medio"])
        _prog_max = 200
        progressao_eixos_completo = sorted(
            ordenado_pior_melhor[:_prog_max],
            key=_progressao_eixo_sort_key,
        )
        ranking_meta = {
            "eixos_listados": len(piores),
            "eixos_com_medicao": len(bloco_scores),
            "eixos_lista_completa": len(progressao_eixos_completo),
            "limite_ranking": 16,
            "lista_completa_cortada": len(bloco_scores) > _prog_max,
        }

        return {
            "origem": "mapa_controle_execucao",
            "descricao_curta": "Progressão física média por eixo (mapa de serviço): destaca eixos com menor % médio de execução; não compara prazos nem cronograma.",
            "agrupamento_eixo": "setor_bloco" if use_setor_grupo else "bloco",
            "ranking_progressao_meta": ranking_meta,
            "kpis": {
                "total_itens": total,
                "percentual_medio": pct_medio,
                "concluidos": concluidos,
                "em_andamento": em_andamento,
                "nao_iniciados": nao_iniciados,
            },
            "blocos_mais_atrasados": piores,
            "progressao_eixos_completo": progressao_eixos_completo,
            "blocos_mais_avancados": melhores,
        }

    def _build_heatmap(self) -> dict[str, Any]:
        """Matriz bloco × pavimento com % médio e criticidade (somente controle)."""
        qs = self.controle_base_queryset()
        items = list(qs.only("setor", "bloco", "pavimento", "status_percentual", "status_texto"))
        n_set = len({_norm_key(i.setor) for i in items if (str(i.setor or "")).strip()})
        use_sg = n_set >= 2

        agg: dict[tuple, list[float]] = {}
        cell_pair_votes: dict[tuple, Counter[tuple[str, str]]] = defaultdict(Counter)

        for item in items:
            ratio = _status_to_ratio(item)
            if ratio is None:
                continue
            p = (item.pavimento or "").strip() or "-"
            raw_s = (str(item.setor or "")).strip()
            raw_b = (str(item.bloco or "")).strip()
            bn = _norm_key(item.bloco) or "SEM BLOCO"
            if use_sg:
                sn = _norm_key(item.setor)
                sn_g = sn if sn else "SEM SETOR"
                key = (sn_g, bn, p)
                if raw_s or raw_b:
                    cell_pair_votes[key][(raw_s, raw_b)] += 1
            else:
                key = (bn, p)
                if raw_b:
                    cell_pair_votes[key][("", raw_b)] += 1
            agg.setdefault(key, []).append(ratio)

        celulas = []
        for gkey, ratios in agg.items():
            avg = sum(ratios) / len(ratios)
            pct = round(avg * 100, 1)
            votes = cell_pair_votes.get(gkey, Counter())
            if use_sg:
                sk, bk, p = gkey[0], gkey[1], gkey[2]
                rotulo, rs, rb = _representative_setor_bloco_from_votes(votes, sk, bk)
                if not rb:
                    rb = _representative_bloco_label(bk, _pair_votes_to_bloco_counter(votes))
                setor_norm_out = sk if sk and sk != "SEM SETOR" else ""
            else:
                bk, p = gkey[0], gkey[1]
                sk = ""
                rotulo, rs, rb = _representative_setor_bloco_from_votes(votes, "", bk)
                if not rb:
                    rb = _representative_bloco_label(bk, _pair_votes_to_bloco_counter(votes))
                setor_norm_out = ""

            celulas.append(
                {
                    "rotulo": rotulo,
                    "setor": rs,
                    "bloco": rb,
                    "setor_norm": setor_norm_out,
                    "bloco_norm": bk,
                    "pavimento": p,
                    "percentual_medio": pct,
                    "amostras": len(ratios),
                    "criticidade": _criticidade_from_pct(pct),
                }
            )
        celulas.sort(key=lambda c: c["percentual_medio"])

        blocos = sorted({c["rotulo"] for c in celulas})[:24]
        pavs = sorted({c["pavimento"] for c in celulas})[:18]

        return {
            "origem": "mapa_controle_execucao",
            "descricao_curta": "Criticidade consolidada apenas do avanço físico (não mistura suprimento nem diário).",
            "agrupamento_eixo": "setor_bloco" if use_sg else "bloco",
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

        # Um RDO por data (o mais recente se houver colisão) — para link do gráfico → detalhe do diário.
        relatorio_id_por_data: dict[date, int] = {}
        for d in diarios_aprovados.order_by("date", "-created_at"):
            if d.date not in relatorio_id_por_data:
                relatorio_id_por_data[d.date] = d.id

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
        ocorrencias_por_dia = []
        for row in por_dia:
            dia = row["diary__date"]
            ocorrencias_por_dia.append(
                {
                    "data": dia.isoformat(),
                    "total": row["n"],
                    "relatorio_id": relatorio_id_por_data.get(dia),
                }
            )
        dias_com_ocorrencia = len(ocorrencias_por_dia)
        media_dia_com_evento = round((total_ocorrencias / dias_com_ocorrencia), 2) if dias_com_ocorrencia else 0.0
        dias_periodo = max(1, (d2 - d1).days + 1)
        taxa_dias_com_ocorrencia = round((dias_com_ocorrencia / dias_periodo) * 100.0, 1)

        tags_qs = (
            OccurrenceTag.objects.filter(occurrences__in=occ_qs)
            .annotate(n=Count("occurrences", filter=Q(occurrences__in=occ_qs), distinct=True))
            .order_by("-n", "name")[:12]
        )
        tags_top = [
            {"id": t.id, "nome": t.name, "cor": t.color or "#64748b", "total": t.n} for t in tags_qs
        ]

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
                    "relatorio_id": occ.diary_id,
                    "descricao": (occ.description or "")[:220],
                    "gravidade": severity,
                    "tags": tags_list[:5],
                }
            )

        recent = (
            diarios_aprovados.order_by("-date")
            .prefetch_related(
                Prefetch(
                    "occurrences",
                    queryset=DiaryOccurrence.objects.prefetch_related("tags").order_by("-created_at"),
                )
            )[:12]
        )
        timeline = []
        for d in recent:
            day_occurrences = list(d.occurrences.all())
            occ_n = len(day_occurrences)
            occ_items = []
            for occ in day_occurrences:
                occ_items.append(
                    {
                        "descricao": (occ.description or "")[:260],
                        "tags": [t.name for t in occ.tags.all()[:4]],
                    }
                )
            timeline.append(
                {
                    "data": d.date.isoformat(),
                    "relatorio": d.report_number,
                    "relatorio_id": d.id,
                    "status": d.status,
                    "ocorrencias_no_dia": occ_n,
                    "resumo_clima": (d.weather_conditions or "")[:160],
                    "ocorrencias": occ_items,
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

        piores_blocos: dict[str, Any] = {}
        for b in controle.get("blocos_mais_atrasados") or []:
            sn = (b.get("setor_norm") or "").strip()
            bn = (b.get("bloco_norm") or _norm_key(b.get("bloco")) or "").strip()
            if sn and bn:
                k = f"{sn}|{bn}"
            elif bn:
                k = bn
            else:
                k = (_norm_key(b.get("rotulo")) or "").strip()
            if k:
                piores_blocos[k] = b

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
                        "rotulo_exibicao": (ctrl.get("rotulo") or "").strip(),
                        "bloco_mapa": (ctrl.get("bloco") or "").strip() or bloco_key,
                        "setor_mapa": (ctrl.get("setor") or "").strip(),
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
        for c in candidatos[:4]:
            local = c.get("local_norm") or "local crítico"
            pri = (c.get("prioridade") or "alta").upper()
            acoes_recomendadas.append(
                {
                    "prioridade": pri,
                    "acao": f"Priorizar frente do {local}: alinhar execução e suprimentos no mesmo turno.",
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
            "acoes_recomendadas": acoes_recomendadas[:8],
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
