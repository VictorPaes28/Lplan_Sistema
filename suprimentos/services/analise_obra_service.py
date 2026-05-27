"""
Agregação para a página **Análise da Obra**: separa semanticamente três fontes:

- **controle** — `AmbienteVersao.layout` (mapa de controle por ambiente operacional da obra).
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
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Prefetch, Q

from django.utils import timezone

from core.models import ConstructionDiary, DiaryOccurrence, DiaryStatus, OccurrenceTag, Project
from mapa_obras.models import Obra
from suprimentos.services.mapa_controle_service import MapaControleFilters, MapaControleService
from suprimentos.services.mapa_controle_viewmodel import (
    _append_pct_for_average,
    _cell_pct_for_average,
    _is_total_header_label,
)


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


def _resolve_gestao_obra(mapa_obra: Obra):
    """Resolve `gestao_aprovacao.Obra` a partir da obra do Mapa (project ou código)."""
    from gestao_aprovacao.models import Obra as GestaoObra

    if mapa_obra.project_id:
        go = GestaoObra.objects.filter(project_id=mapa_obra.project_id).first()
        if go:
            return go
    project = _resolve_project_for_obra(mapa_obra)
    if project:
        go = GestaoObra.objects.filter(project_id=project.id).first()
        if go:
            return go
    codigo = (mapa_obra.codigo_sienge or "").strip()
    if codigo:
        return GestaoObra.objects.filter(codigo=codigo).first()
    return None


def _workorder_valor_para_soma(wo) -> Decimal:
    if wo.valor_estimado is not None:
        return wo.valor_estimado
    if wo.valor_medicao is not None:
        return wo.valor_medicao
    return Decimal("0")


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


def _norm_header_col(value: object) -> str:
    text = (str(value or "")).strip().upper()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("ASCII")
    return " ".join(text.split())


def _find_header_col(header: list, *tokens: str) -> int | None:
    wanted = {_norm_header_col(t) for t in tokens if t}
    for idx, cell in enumerate(header):
        hn = _norm_header_col(cell)
        if not hn:
            continue
        if hn in wanted:
            return idx
        for w in wanted:
            if w and w in hn:
                return idx
    return None


def _parse_layout_matrix_rows(layout: dict | None) -> list[list[str]]:
    if not isinstance(layout, dict):
        return []
    sections = layout.get("sections")
    if not isinstance(sections, list):
        return []
    for section in sections:
        if not isinstance(section, dict):
            continue
        if str(section.get("kind") or "").strip() not in {"matrix_table", "table"}:
            continue
        data = section.get("data") if isinstance(section.get("data"), dict) else {}
        rows = data.get("rows")
        if not isinstance(rows, list) or not rows:
            continue
        out: list[list[str]] = []
        for row in rows:
            if isinstance(row, list):
                out.append([str(c or "").strip() for c in row])
            else:
                out.append([str(row or "").strip()])
        return out
    return []


def _parse_total_pct_cell(value: object) -> float | None:
    parsed = _cell_pct_for_average(value)
    if parsed is None:
        return None
    try:
        return float(parsed)
    except (TypeError, ValueError):
        return None


def _collect_activity_pcts_from_values(atividades: dict[str, str] | None) -> list[float]:
    """
    Mesma regra do mapa clássico (AmbienteProvider): cada célula de atividade preenchida
  entra na média; vazio → 0%; \"-\" / N/A não entra no denominador.
    """
    bucket: list[float] = []
    acts = atividades if isinstance(atividades, dict) else {}
    for val in acts.values():
        _append_pct_for_average(bucket, val)
    return bucket


def _avg_pct_from_activity_values(atividades: dict[str, str] | None) -> float:
    values = _collect_activity_pcts_from_values(atividades)
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _collect_all_activity_pcts_from_rows(rows: list[dict[str, Any]]) -> list[float]:
    out: list[float] = []
    for row in rows:
        out.extend(_collect_activity_pcts_from_values(row.get("atividades")))
    return out


def _apto_status_bucket(total_pct: float) -> str:
    if total_pct >= 100.0 or total_pct >= 99.9:
        return "concluido"
    if total_pct <= 0.0:
        return "nao_iniciado"
    return "em_andamento"


def _activity_cell_ratio(value: object) -> float | None:
    parsed = _parse_total_pct_cell(value)
    if parsed is None:
        return None
    return max(0.0, min(1.0, parsed / 100.0))


MENSAGEM_CONTROLE_SEM_MAPA = "Nenhum mapa de controle criado para esta obra"


# Frases que não devem disparar nível máximo (prevenção / ausência de evento).
_PREVENCAO_ACIDENTE_RE = re.compile(
    "|".join(
        [
            r"\bevitar\s+acidentes?\b",
            r"\bpara\s+evitar\s+acidentes?\b",
            r"\bpreven[çc][aã]o\s+(?:de\s+)?acidentes?\b",
            r"\breduz(?:ir|indo)?\s+(?:o\s+)?risco\s+(?:de\s+)?acidentes?\b",
            r"\bsem\s+acidentes?\b",
            r"\bn[aã]o\s+houve\s+acidentes?\b",
            r"\bn[aã]o\s+ocorreram?\s+acidentes?\b",
            r"\bnenhum\s+acidente\b",
            r"\bzero\s+acidentes?\b",
        ]
    ),
    re.IGNORECASE,
)

# Quedas operacionais frequentes — não são “evento físico crítico” para este painel.
_QUEDA_OPERACIONAL_RE = re.compile(
    r"queda\s+de\s+(?:energia|tens[aã]o|press[aã]o|fornecimento|internet|sinal)",
    re.IGNORECASE,
)


def _normalize_occurrence_text(description: str, tag_names: list[str]) -> str:
    raw = " ".join([description or ""] + list(tag_names or []))
    return raw.casefold()


def _strip_prevention_phrases(text_cf: str) -> str:
    """Remove trechos de prevenção para classificar impacto sem falso ‘urgente’."""
    t = _PREVENCAO_ACIDENTE_RE.sub(" ", text_cf)
    return re.sub(r"\s+", " ", t).strip()


def _classify_occurrence_severity(description: str, tag_names: list[str]) -> str:
    """
    Classifica severidade para leitura executiva.

    Usa texto normalizado + remoção de frases típicas de prevenção (ex.: «evitar acidentes»),
    depois palavras-chave por nível. Não substitui julgamento humano no canteiro.
    """
    raw_cf = _normalize_occurrence_text(description, tag_names)
    t = _strip_prevention_phrases(raw_cf)

    # --- Crítica: evento grave, interdição, incidente real (após remover prevenção pura).
    _crit_geo = (
        "embargo",
        "interdicao",
        "interdição",
        "colapso",
        "desabamento",
        "deslizamento",
        "incêndio",
        "incendio",
        "explosão",
        "explosao",
    )
    if any(k in t for k in _crit_geo):
        return "critica"

    if re.search(r"\b(houve|ocorreu|registrado|vitima|vítima|vitimas|vítimas|obito|óbito|fatalidades?)\b", t):
        return "critica"
    if "fatal" in t and "nao fatal" not in t and "não fatal" not in t:
        return "critica"
    if "morte" in t or "óbito" in t or "obito" in t:
        return "critica"

    if re.search(r"\bacidentes?\b", t):
        return "critica"

    if "queda" in t:
        if _QUEDA_OPERACIONAL_RE.search(t):
            return "alta"
        return "critica"

    if "grave" in t:
        if not any(x in t for x in ("nao grave", "não grave", "sem gravidade", "baixa gravidade", "gravidade leve")):
            return "critica"

    # --- Atraso leve / pontual → média (antes de “atraso” genérico → alta).
    if re.search(
        r"(?:leve|ligeiro|pequeno|pontual|moderado)\s+atraso|atraso\s+(?:leve|ligeiro|pequeno|pontual|moderado)",
        t,
    ):
        return "media"

    # --- Alta: bloqueio, parada explícita, falha, risco (não catastrófico).
    if re.search(r"\batraso\b", t) or re.search(r"\bparada\b", t) or "paralisa" in t or "paralisado" in t:
        return "alta"
    if any(k in t for k in ("enchente", "alagamento", "enxurrada")):
        return "alta"
    if any(
        k in t
        for k in (
            "bloqueio",
            "bloqueada",
            "interromp",
            "falha",
            "indisponivel",
            "indisponível",
            "risco",
        )
    ):
        return "alta"
    if any(k in t for k in ("seguranca", "segurança")):
        return "alta"
    # "erro" só com contexto mais forte — evita ruído de “erro de digitação”.
    if re.search(r"\berro\s+(?:de|na|no|em)\b", t) or "erro operacional" in t:
        return "alta"

    # --- Média: impacto moderado, planejamento, documentação.
    _media_kw = (
        "pendencia",
        "pendência",
        "retrabalho",
        "retrabalhar",
        "ajuste",
        "ajustar",
        "nao conforme",
        "não conforme",
        "desvio",
        "inspecao",
        "inspeção",
        "vistoria",
        "nao conformidade",
        "não conformidade",
        "correcao pontual",
        "correção pontual",
        "laudo pendente",
        "documentacao pendente",
        "documentação pendente",
        "replanejamento",
        "replanejar",
        "revisao de cronograma",
        "revisão de cronograma",
        "cronograma impactado",
        "impacto moderado",
        "equipe reduzida",
        "falta de mao de obra",
        "falta de mão de obra",
        "mao de obra reduzida",
        "mão de obra reduzida",
        "aguardando material",
        "material em transito",
        "material em trânsito",
        "treinamento",
        "orientacao de seguranca",
        "orientação de segurança",
        "dds",
    )
    if any(k in t for k in _media_kw):
        return "media"
    if re.search(r"\bpendente\s+(?:de\s+)?(?:documento|liberacao|liberação|assinatura)\b", t):
        return "media"

    # --- Baixa: rotina explícita / evolução normal / só clima sem paralisação grave.
    _baixa_kw = (
        "sem intercorrencia",
        "sem intercorrência",
        "sem ocorrencia relevante",
        "sem ocorrência relevante",
        "sem incidentes",
        "dia normal",
        "rotina",
        "conforme planejado",
        "conforme o planejado",
        "dentro do cronograma",
        "dentro do prazo",
        "evolucao positiva",
        "evolução positiva",
        "andamento normal",
        "tempo bom",
        "tempo firme",
        "clima favoravel",
        "clima favorável",
        "condicoes normais",
        "condições normais",
        "servicos normais",
        "serviços normais",
        "atividades normais",
    )
    if any(k in t for k in _baixa_kw):
        return "baixa"
    # Meteorologia registrada sem bloqueio / paralisação / enchente (já tratados acima).
    if re.search(r"\b(chuva|chuvas|garoa|garoando|umidade|vento)\b", t):
        if not any(
            x in t
            for x in (
                "paralis",
                "interromp",
                "bloqueio",
                "impossibilit",
                "inviavel",
                "inviável",
                "enchente",
                "alagamento",
                "deslizamento",
            )
        ):
            return "baixa"

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
        self._controle_bundle_cache: dict[str, Any] | None = None

    def controle_ambiente_cache_stamp(self) -> str:
        """Carimbo para invalidar cache do BI quando o ambiente de mapa for editado."""
        bundle = self._load_controle_bundle()
        if not bundle:
            return "sem_mapa"
        updated = bundle.get("ambiente_updated_at")
        ambiente_id = bundle.get("ambiente_id")
        if updated is not None:
            try:
                return f"{ambiente_id}:{updated.isoformat()}"
            except AttributeError:
                return f"{ambiente_id}:{updated}"
        return f"{ambiente_id}:0"

    def _load_controle_bundle(self) -> dict[str, Any] | None:
        if self._controle_bundle_cache is not None:
            return self._controle_bundle_cache
        self._controle_bundle_cache = self.controle_base_from_ambiente(self.obra)
        return self._controle_bundle_cache

    def controle_base_from_ambiente(self, obra: Obra) -> dict[str, Any] | None:
        from painel_operacional.models import AmbienteOperacional, AmbienteTipo, AmbienteVersao, VersaoEstado

        ambiente = (
            AmbienteOperacional.objects.filter(
                obra_id=obra.id,
                tipo=AmbienteTipo.MAPA_CONTROLE,
                ativo=True,
            )
            .order_by("-updated_at")
            .first()
        )
        if not ambiente:
            return None

        versao = (
            ambiente.versoes.filter(estado=VersaoEstado.DRAFT).order_by("-numero").first()
        )
        if not versao:
            versao = (
                ambiente.versoes.filter(estado=VersaoEstado.PUBLISHED).order_by("-numero").first()
            )
        if not versao:
            return None

        rows = self._parse_layout_rows(versao.layout if isinstance(versao.layout, dict) else {})
        return {
            "ambiente_id": ambiente.id,
            "ambiente_updated_at": ambiente.updated_at,
            "rows": rows,
        }

    def _parse_layout_rows(self, layout: dict) -> list[dict[str, Any]]:
        matrix = _parse_layout_matrix_rows(layout)
        if not matrix:
            return []

        header = matrix[0]
        idx_setor = _find_header_col(header, "SETOR", "REGIAO")
        idx_bloco = _find_header_col(header, "BLOCO", "TORRE", "LOCAL")
        idx_pav = _find_header_col(header, "PAVIMENTO", "PAV", "ANDAR", "NIVEL")
        idx_apto = _find_header_col(header, "APTO", "UNIDADE", "UND", "LOCAL")

        idx_total = None
        for idx, cell in enumerate(header):
            if _is_total_header_label(str(cell or "")):
                idx_total = idx
                break
        if idx_total is None and len(header) > 0:
            idx_total = len(header) - 1

        axis_max = max(
            [i for i in (idx_setor, idx_bloco, idx_pav, idx_apto) if isinstance(i, int)],
            default=-1,
        )
        activity_cols: list[tuple[int, str]] = []
        for idx in range(axis_max + 1, len(header)):
            if idx == idx_total:
                continue
            label = str(header[idx] or "").strip() or f"Atividade {idx}"
            if _is_total_header_label(label):
                continue
            activity_cols.append((idx, label))

        parsed: list[dict[str, Any]] = []
        for row in matrix[1:]:
            if not row:
                continue
            while len(row) < len(header):
                row.append("")

            apto = (
                str(row[idx_apto] if isinstance(idx_apto, int) and idx_apto < len(row) else "")
                .strip()
            )
            if not apto:
                continue

            setor = (
                str(row[idx_setor] if isinstance(idx_setor, int) and idx_setor < len(row) else "")
                .strip()
            )
            bloco = (
                str(row[idx_bloco] if isinstance(idx_bloco, int) and idx_bloco < len(row) else "")
                .strip()
            )
            pavimento = (
                str(row[idx_pav] if isinstance(idx_pav, int) and idx_pav < len(row) else "")
                .strip()
            )

            atividades: dict[str, str] = {}
            for col_idx, col_name in activity_cols:
                if col_idx < len(row):
                    atividades[col_name] = str(row[col_idx] or "").strip()

            # Ignora Total gravado no JSON — recalcula como média das colunas de atividade (mapa clássico).
            total_pct = _avg_pct_from_activity_values(atividades)

            parsed.append(
                {
                    "setor": setor,
                    "bloco": bloco,
                    "pavimento": pavimento,
                    "apto": apto,
                    "total_pct": total_pct,
                    "atividades": atividades,
                    "activity_pcts": _collect_activity_pcts_from_values(atividades),
                }
            )
        return parsed

    def _filter_controle_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        f = self.filtros
        out: list[dict[str, Any]] = []
        for row in rows:
            if f.setor and (row.get("setor") or "").strip() != f.setor.strip():
                continue
            if f.bloco and (row.get("bloco") or "").strip() != f.bloco.strip():
                continue
            if f.pavimento and (row.get("pavimento") or "").strip() != f.pavimento.strip():
                continue
            if f.apto and (row.get("apto") or "").strip() != f.apto.strip():
                continue
            if f.atividade:
                needle = f.atividade.strip().lower()
                acts = row.get("atividades") if isinstance(row.get("atividades"), dict) else {}
                if not any(needle in str(k).lower() or needle in str(v).lower() for k, v in acts.items()):
                    continue
            if f.status_servico in {"concluido", "em_andamento", "nao_iniciado"}:
                bucket = _apto_status_bucket(float(row.get("total_pct") or 0))
                if bucket != f.status_servico:
                    continue
            out.append(row)
        return out

    def _controle_sem_dados_payload(self, mensagem: str | None = None) -> dict[str, Any]:
        return {
            "sem_dados": True,
            "mensagem": mensagem or MENSAGEM_CONTROLE_SEM_MAPA,
            "origem": "mapa_controle_ambiente",
            "descricao_curta": "Progressão física a partir do mapa de controle do ambiente operacional.",
            "agrupamento_eixo": "bloco",
            "ranking_progressao_meta": {
                "eixos_listados": 0,
                "eixos_com_medicao": 0,
                "eixos_lista_completa": 0,
                "limite_ranking": 16,
                "lista_completa_cortada": False,
            },
            "kpis": {
                "total_itens": 0,
                "percentual_medio": None,
                "concluidos": 0,
                "em_andamento": 0,
                "nao_iniciados": 0,
            },
            "blocos_mais_atrasados": [],
            "progressao_eixos_completo": [],
            "blocos_mais_avancados": [],
        }

    def _build_controle_ranking_rows(
        self, rows: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], bool]:
        setores_ns = {_norm_key(r.get("setor")) for r in rows if (str(r.get("setor") or "")).strip()}
        use_setor_grupo = len(setores_ns) >= 2

        by_eixo: dict[str, list[float]] = {}
        pair_votes: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)

        for row in rows:
            cell_values = row.get("activity_pcts")
            if not isinstance(cell_values, list) or not cell_values:
                cell_values = _collect_activity_pcts_from_values(row.get("atividades"))
            if not cell_values:
                continue
            sn = _norm_key(row.get("setor"))
            bn = _norm_key(row.get("bloco")) or "SEM BLOCO"
            raw_s = (str(row.get("setor") or "")).strip()
            raw_b = (str(row.get("bloco") or "")).strip()

            if use_setor_grupo:
                sn_g = sn if sn else "SEM SETOR"
                gkey = f"{sn_g}{EIXO_SETOR_BLOCO_SEP}{bn}"
            else:
                gkey = bn

            by_eixo.setdefault(gkey, []).extend(float(v) for v in cell_values)
            if use_setor_grupo:
                if raw_s or raw_b:
                    pair_votes[gkey][(raw_s, raw_b)] += 1
            elif raw_b:
                pair_votes[gkey][("", raw_b)] += 1

        bloco_scores: list[dict[str, Any]] = []
        for gkey, values in by_eixo.items():
            if not values:
                continue
            avg = sum(values) / len(values)
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

            bloco_scores.append(
                {
                    "rotulo": rotulo,
                    "setor": rs,
                    "bloco": rb,
                    "setor_norm": setor_norm_out,
                    "bloco_norm": bk,
                    "percentual_medio": round(avg, 1),
                    "amostras": len(values),
                }
            )
        return bloco_scores, use_setor_grupo

    def _build_gestcontroll(self) -> dict[str, Any]:
        """Pedidos / aprovações (GestControll) para a obra do mapa e o período do BI."""
        from gestao_aprovacao.models import Approval, WorkOrder

        empty: dict[str, Any] = {
            "gestao_obra_id": None,
            "kpis": {
                "pendentes_count": 0,
                "pendentes_valor": 0.0,
                "reprovados_count": 0,
                "reprovados_por_tipo": {},
                "taxa_aprovacao": 0,
                "taxa_reprovacao_pct": 0.0,
                "aprovados_count": 0,
                "alcadas_travadas": 0,
                "alcadas_detalhes": [],
                "tempo_medio_geral": None,
            },
            "pedidos_pendentes": [],
            "aprovadores": [],
        }

        go = _resolve_gestao_obra(self.obra)
        if not go:
            return empty

        tz = timezone.get_current_timezone()
        start_dt = timezone.make_aware(datetime.combine(self.periodo.data_inicio, time.min), tz)
        end_exclusive = timezone.make_aware(
            datetime.combine(self.periodo.data_fim + timedelta(days=1), time.min),
            tz,
        )
        now = timezone.now()
        stale_cutoff = now - timedelta(days=5)

        base = WorkOrder.objects.filter(obra=go)
        pend_qs = base.filter(status__in=["pendente", "reaprovacao"]).order_by("-data_envio", "-created_at")

        pendentes_count = pend_qs.count()
        pendentes_valor_dec = Decimal("0")
        for wo in pend_qs.only("valor_estimado", "valor_medicao"):
            pendentes_valor_dec += _workorder_valor_para_soma(wo)

        pedidos_pendentes: list[dict[str, Any]] = []
        for wo in pend_qs[:15]:
            ref = wo.data_envio or wo.created_at
            dias_pendente = max(0, (now - ref).days) if ref else 0
            pedidos_pendentes.append(
                {
                    "id": wo.id,
                    "codigo": wo.codigo,
                    "nome_credor": wo.nome_credor,
                    "tipo_solicitacao": wo.get_tipo_solicitacao_display(),
                    "dias_pendente": dias_pendente,
                    "valor_estimado": wo.valor_estimado,
                    "valor_medicao": wo.valor_medicao,
                }
            )

        approvals_list = list(
            Approval.objects.filter(
                work_order__obra=go,
                created_at__gte=start_dt,
                created_at__lt=end_exclusive,
            ).select_related("aprovado_por", "work_order")
        )

        aprovados_count = sum(1 for a in approvals_list if a.decisao == "aprovado")
        reprovados_list = [a for a in approvals_list if a.decisao == "reprovado"]
        reprovados_count = len(reprovados_list)

        rep_by_tipo: Counter[str] = Counter()
        for ap in reprovados_list:
            rep_by_tipo[ap.work_order.get_tipo_solicitacao_display()] += 1
        reprovados_por_tipo = dict(rep_by_tipo.most_common())

        total_dec = aprovados_count + reprovados_count
        taxa_aprovacao = round(100 * aprovados_count / total_dec) if total_dec else 0
        taxa_reprovacao_pct = round(100 * reprovados_count / total_dec, 1) if total_dec else 0.0

        stale_qs = base.filter(status__in=["pendente", "reaprovacao"]).filter(
            Q(data_envio__isnull=False, data_envio__lt=stale_cutoff)
            | Q(data_envio__isnull=True, created_at__lt=stale_cutoff)
        )
        alcadas_travadas = stale_qs.count()
        stale_by_tipo: Counter[str] = Counter()
        for wo in stale_qs.only("tipo_solicitacao"):
            stale_by_tipo[wo.get_tipo_solicitacao_display()] += 1
        alcadas_detalhes = [{"nome": k, "count": v} for k, v in stale_by_tipo.most_common()]

        all_tempos: list[float] = []
        for ap in approvals_list:
            wo = ap.work_order
            env = wo.data_envio or wo.created_at
            if env and ap.created_at:
                delta = (ap.created_at - env).total_seconds() / 86400.0
                if delta >= 0:
                    all_tempos.append(delta)
        tempo_medio_geral = round(sum(all_tempos) / len(all_tempos), 1) if all_tempos else None

        by_user: dict[int, dict[str, Any]] = {}
        for ap in approvals_list:
            u = ap.aprovado_por
            if not u:
                continue
            uid = u.id
            if uid not in by_user:
                by_user[uid] = {
                    "nome": (u.get_full_name() or "").strip() or u.username,
                    "nivel": None,
                    "aprovados": 0,
                    "reprovados": 0,
                    "tempos": [],
                }
            st = by_user[uid]
            if ap.decisao == "aprovado":
                st["aprovados"] += 1
            else:
                st["reprovados"] += 1
            wo = ap.work_order
            env = wo.data_envio or wo.created_at
            if env and ap.created_at:
                delta = (ap.created_at - env).total_seconds() / 86400.0
                if delta >= 0:
                    st["tempos"].append(delta)

        aprovadores: list[dict[str, Any]] = []
        for st in sorted(
            by_user.values(),
            key=lambda x: x["aprovados"] + x["reprovados"],
            reverse=True,
        ):
            tempos = st["tempos"]
            tm = round(sum(tempos) / len(tempos), 1) if tempos else 99.0
            aprovadores.append(
                {
                    "nome": st["nome"],
                    "nivel": st["nivel"],
                    "aprovados": st["aprovados"],
                    "reprovados": st["reprovados"],
                    "tempo_medio_dias": tm,
                }
            )

        return {
            "gestao_obra_id": go.id,
            "kpis": {
                "pendentes_count": pendentes_count,
                "pendentes_valor": float(pendentes_valor_dec.quantize(Decimal("0.01"))),
                "reprovados_count": reprovados_count,
                "reprovados_por_tipo": reprovados_por_tipo,
                "taxa_aprovacao": taxa_aprovacao,
                "taxa_reprovacao_pct": taxa_reprovacao_pct,
                "aprovados_count": aprovados_count,
                "alcadas_travadas": alcadas_travadas,
                "alcadas_detalhes": alcadas_detalhes,
                "tempo_medio_geral": tempo_medio_geral,
            },
            "pedidos_pendentes": pedidos_pendentes,
            "aprovadores": aprovadores,
        }

    def _build_restricoes(self) -> dict[str, Any]:
        """Restrições (impedimentos) da obra GestControll vinculada ao mapa."""
        from impedimentos.models import Impedimento, StatusImpedimento

        prio_template = {
            Impedimento.PRIORIDADE_CRITICA: 0,
            Impedimento.PRIORIDADE_ALTA: 0,
            Impedimento.PRIORIDADE_NORMAL: 0,
            Impedimento.PRIORIDADE_BAIXA: 0,
        }
        empty: dict[str, Any] = {
            "kpis": {
                "total_aberto": 0,
                "por_prioridade": dict(prio_template),
                "vencidas": 0,
                "sem_responsavel": 0,
                "subtarefas_bloqueando": 0,
                "restricoes_com_subtarefa_aberta": 0,
            },
            "vencidas_recentes": [],
            "por_responsavel": [],
        }

        go = _resolve_gestao_obra(self.obra)
        if not go:
            return empty

        ultimo = StatusImpedimento.objects.filter(obra=go).order_by("-ordem").first()
        hoje = timezone.now().date()

        roots = Impedimento.objects.filter(obra=go, parent__isnull=True)
        if ultimo:
            base_open = roots.exclude(status_id=ultimo.id)
        else:
            base_open = roots

        total_aberto = base_open.count()
        por_prioridade = dict(prio_template)
        for row in base_open.values("prioridade").annotate(c=Count("id")):
            k = row["prioridade"]
            if k in por_prioridade:
                por_prioridade[k] = row["c"]

        vencidas_qs = base_open.filter(prazo__isnull=False, prazo__lt=hoje)
        vencidas = vencidas_qs.count()

        def _resp_label(imp) -> str:
            names = [
                (u.get_full_name() or "").strip() or u.username for u in imp.responsaveis.all()
            ]
            return ", ".join(names) if names else ""

        vencidas_recentes: list[dict[str, Any]] = []
        ve_ord = vencidas_qs.prefetch_related("responsaveis").order_by("prazo")[:2]
        for imp in ve_ord:
            pr = imp.prazo
            dias_vencido = int((hoje - pr).days) if pr else 0
            rl = _resp_label(imp)
            vencidas_recentes.append(
                {
                    "titulo": imp.titulo,
                    "dias_vencido": dias_vencido,
                    "prioridade": imp.get_prioridade_display(),
                    "responsavel": rl or None,
                }
            )

        sem_responsavel = (
            base_open.annotate(_nresp=Count("responsaveis")).filter(_nresp=0).count()
        )

        resp_ct: Counter[str] = Counter()
        for imp in base_open.prefetch_related("responsaveis"):
            for u in imp.responsaveis.all():
                nome = (u.get_full_name() or "").strip() or u.username
                resp_ct[nome] += 1
        por_responsavel = [{"nome": n, "total": t} for n, t in resp_ct.most_common()]

        open_subs = Impedimento.objects.filter(obra=go).exclude(parent__isnull=True)
        if ultimo:
            open_subs = open_subs.exclude(status_id=ultimo.id)
        subtarefas_bloqueando = open_subs.count()

        open_root_ids = frozenset(base_open.values_list("pk", flat=True))
        roots_with_open_sub: set[int] = set()
        for imp in open_subs.select_related("parent", "parent__parent"):
            p = imp.parent
            if p is None:
                continue
            rid = p.parent_id if p.parent_id else p.id
            if rid in open_root_ids:
                roots_with_open_sub.add(rid)
        restricoes_com_subtarefa_aberta = len(roots_with_open_sub)

        return {
            "kpis": {
                "total_aberto": total_aberto,
                "por_prioridade": por_prioridade,
                "vencidas": vencidas,
                "sem_responsavel": sem_responsavel,
                "subtarefas_bloqueando": subtarefas_bloqueando,
                "restricoes_com_subtarefa_aberta": restricoes_com_subtarefa_aberta,
            },
            "vencidas_recentes": vencidas_recentes,
            "por_responsavel": por_responsavel,
        }

    def build_filtros_payload(self) -> dict[str, Any]:
        """Opções de dropdown e valores aplicados (para UI e API)."""
        bundle = self._load_controle_bundle()
        base_rows = bundle.get("rows", []) if bundle else []
        setores = sorted({(r.get("setor") or "").strip() for r in base_rows if (r.get("setor") or "").strip()})[:120]
        blocos = sorted({(r.get("bloco") or "").strip() for r in base_rows if (r.get("bloco") or "").strip()})[:120]
        pavs = sorted(
            {(r.get("pavimento") or "").strip() for r in base_rows if (r.get("pavimento") or "").strip()}
        )[:80]
        aptos = sorted({(r.get("apto") or "").strip() for r in base_rows if (r.get("apto") or "").strip()})[:200]
        atividades_set: set[str] = set()
        for r in base_rows:
            acts = r.get("atividades") if isinstance(r.get("atividades"), dict) else {}
            for name in acts:
                label = str(name or "").strip()
                if label:
                    atividades_set.add(label)
        atividades = sorted(atividades_set)[:200]

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
        rdos = diario.get("rdos_resumo") if isinstance(diario.get("rdos_resumo"), dict) else {}
        rdos_pend_hero = int(rdos.get("pendentes_rdos_count") or 0)
        cruzamento = self._build_cruzamento(controle, suprimentos, diario)
        heatmap = self._build_heatmap()
        situacao = self._classify_situacao(controle, suprimentos, diario)
        filtros = self.build_filtros_payload()
        gestcontroll = self._build_gestcontroll()
        restricoes = self._build_restricoes()
        gv = gestcontroll["kpis"]["pendentes_valor"]

        return {
            "meta": {
                "obra_id": self.obra.id,
                "obra_nome": self.obra.nome,
                "obra_codigo": self.obra.codigo_sienge,
                "projeto_diario_id": project.id if project else None,
                "projeto_diario_codigo": project.code if project else None,
                "projeto_diario_nome": project.name if project else None,
                "periodo": {
                    "inicio": self.periodo.data_inicio.isoformat(),
                    "fim": self.periodo.data_fim.isoformat(),
                    "dias": dias_periodo,
                },
                "gerado_em": timezone.now().isoformat(),
                "situacao_executiva": situacao,
                "kpis_hero": {
                    "valor_em_aprovacao": gv,
                    "restricoes_abertas": restricoes["kpis"]["total_aberto"],
                    "rdos_pendentes": rdos_pend_hero,
                },
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
            "gestcontroll": gestcontroll,
            "restricoes": restricoes,
        }

    def build_section(self, secao: str) -> dict[str, Any] | None:
        """Retorna apenas um bloco do payload (para carregamento assíncrono por seção)."""
        s = (secao or "").strip().lower()
        if s in ("", "all", "full"):
            return self.build_payload()
        if s == "meta":
            project = _resolve_project_for_obra(self.obra)
            dias_periodo = max(1, (self.periodo.data_fim - self.periodo.data_inicio).days + 1)
            controle = self._build_controle()
            diario = self._build_diario(project)
            gestcontroll = self._build_gestcontroll()
            restricoes = self._build_restricoes()
            rdos = diario.get("rdos_resumo") if isinstance(diario.get("rdos_resumo"), dict) else {}
            gv = gestcontroll["kpis"]["pendentes_valor"]
            return {
                "meta": {
                    "obra_id": self.obra.id,
                    "obra_nome": self.obra.nome,
                    "obra_codigo": self.obra.codigo_sienge,
                    "projeto_diario_id": project.id if project else None,
                    "projeto_diario_codigo": project.code if project else None,
                    "projeto_diario_nome": project.name if project else None,
                    "periodo": {
                        "inicio": self.periodo.data_inicio.isoformat(),
                        "fim": self.periodo.data_fim.isoformat(),
                        "dias": dias_periodo,
                    },
                    "gerado_em": timezone.now().isoformat(),
                    "situacao_executiva": self._classify_situacao(
                        controle,
                        {"kpis": {}},
                        diario,
                    ),
                    "kpis_hero": {
                        "valor_em_aprovacao": gv,
                        "restricoes_abertas": restricoes["kpis"]["total_aberto"],
                        "rdos_pendentes": int(rdos.get("pendentes_rdos_count") or 0),
                    },
                    "baseline_planejamento": {
                        "disponivel": False,
                        "mensagem": (
                            "Curva planejada × real depende da fonte de baseline definida pelo produto; "
                            "até lá o comparativo oficial de prazo não é exibido automaticamente."
                        ),
                    },
                }
            }
        if s == "filtros":
            return {"filtros": self.build_filtros_payload()}
        if s == "controle":
            return {"controle": self._build_controle()}
        if s == "suprimentos":
            return {"suprimentos": self._build_suprimentos()}
        if s == "diario":
            project = _resolve_project_for_obra(self.obra)
            return {"diario": self._build_diario(project)}
        if s == "heatmap":
            return {"heatmap": self._build_heatmap()}
        if s == "cruzamento":
            project = _resolve_project_for_obra(self.obra)
            controle = self._build_controle()
            suprimentos = self._build_suprimentos()
            diario = self._build_diario(project)
            return {"cruzamento": self._build_cruzamento(controle, suprimentos, diario)}
        return None

    def build_drill_down(self, bloco: str, pavimento: str, setor: str | None = None) -> dict[str, Any]:
        """Detalhe para drawer: recorte do controle + resumo de suprimentos por busca no local."""
        bloco = (bloco or "").strip()
        pavimento = (pavimento or "").strip()
        setor = (setor or "").strip()

        bundle = self._load_controle_bundle()
        base_rows = bundle.get("rows", []) if bundle else []
        scoped = []
        for row in base_rows:
            if bloco and (row.get("bloco") or "").strip() != bloco:
                continue
            if setor and (row.get("setor") or "").strip() != setor:
                continue
            if pavimento and (row.get("pavimento") or "").strip() != pavimento:
                continue
            scoped.append(row)

        itens: list[dict[str, Any]] = []
        for row in scoped:
            total_pct = float(row.get("total_pct") or 0)
            acts = row.get("atividades") if isinstance(row.get("atividades"), dict) else {}
            for act_name, act_val in acts.items():
                ratio = _activity_cell_ratio(act_val)
                itens.append(
                    {
                        "atividade": act_name,
                        "apto": row.get("apto"),
                        "pavimento": row.get("pavimento"),
                        "status_texto": str(act_val or ""),
                        "status_percentual": ratio,
                        "observacao": "",
                    }
                )
            itens.append(
                {
                    "atividade": "Total unidade",
                    "apto": row.get("apto"),
                    "pavimento": row.get("pavimento"),
                    "status_texto": f"{total_pct:.1f}%",
                    "status_percentual": max(0.0, min(1.0, total_pct / 100.0)),
                    "observacao": "",
                }
            )

        ratios: list[float] = []
        concluidos = em_andamento = nao_iniciados = sem_dado = 0
        itens_com_ratio: list[tuple[dict[str, Any], float]] = []
        for row in scoped:
            cell_values = row.get("activity_pcts")
            if not isinstance(cell_values, list) or not cell_values:
                cell_values = _collect_activity_pcts_from_values(row.get("atividades"))
            unit_avg = _avg_pct_from_activity_values(row.get("atividades"))
            unit_ratio = max(0.0, min(1.0, unit_avg / 100.0))
            preview_row = {
                "atividade": "Total unidade",
                "apto": row.get("apto"),
                "pavimento": row.get("pavimento"),
                "status_texto": f"{unit_avg:.1f}%",
                "status_percentual": unit_ratio,
                "observacao": "",
            }
            itens_com_ratio.append((preview_row, unit_ratio))
            bucket = _apto_status_bucket(unit_avg)
            if bucket == "concluido":
                concluidos += 1
            elif bucket == "nao_iniciado":
                nao_iniciados += 1
            else:
                em_andamento += 1
            for pct_val in cell_values:
                ratios.append(max(0.0, min(1.0, float(pct_val) / 100.0)))

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
        bundle = self._load_controle_bundle()
        if not bundle:
            return self._controle_sem_dados_payload()

        rows = self._filter_controle_rows(bundle.get("rows") or [])
        if not rows:
            return self._controle_sem_dados_payload(
                "Nenhuma unidade no mapa de controle corresponde aos filtros aplicados."
            )

        all_values = _collect_all_activity_pcts_from_rows(rows)
        pct_medio = round(sum(all_values) / len(all_values), 2) if all_values else None

        concluidos = sum(1 for v in all_values if v >= 99.5)
        em_andamento = sum(1 for v in all_values if 0 < v < 99.5)
        nao_iniciados = sum(1 for v in all_values if v <= 0)

        bloco_scores, use_setor_grupo = self._build_controle_ranking_rows(rows)

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
            "sem_dados": False,
            "origem": "mapa_controle_ambiente",
            "ambiente_id": bundle.get("ambiente_id"),
            "descricao_curta": (
                "Progressão física média das células de atividade do mapa de controle "
                "(mesma regra do mapa clássico); não compara prazos nem cronograma."
            ),
            "agrupamento_eixo": "setor_bloco" if use_setor_grupo else "bloco",
            "ranking_progressao_meta": ranking_meta,
            "kpis": {
                "total_itens": len(all_values),
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
        bundle = self._load_controle_bundle()
        if not bundle:
            return {
                "origem": "mapa_controle_ambiente",
                "descricao_curta": "Criticidade consolidada apenas do avanço físico (não mistura suprimento nem diário).",
                "agrupamento_eixo": "bloco",
                "blocos_eixo": [],
                "pavimentos_eixo": [],
                "celulas": [],
                "legenda_criticidade": {
                    "critica": "< 30% executado",
                    "alta": "30–55%",
                    "media": "55–75%",
                    "baixa": "≥ 75%",
                    "sem_dado": "Sem amostra válida",
                },
            }

        items = self._filter_controle_rows(bundle.get("rows") or [])
        n_set = len({_norm_key(r.get("setor")) for r in items if (str(r.get("setor") or "")).strip()})
        use_sg = n_set >= 2

        agg: dict[tuple, list[float]] = {}
        cell_pair_votes: dict[tuple, Counter[tuple[str, str]]] = defaultdict(Counter)

        for row in items:
            cell_values = row.get("activity_pcts")
            if not isinstance(cell_values, list) or not cell_values:
                cell_values = _collect_activity_pcts_from_values(row.get("atividades"))
            p = (row.get("pavimento") or "").strip() or "-"
            raw_s = (str(row.get("setor") or "")).strip()
            raw_b = (str(row.get("bloco") or "")).strip()
            bn = _norm_key(row.get("bloco")) or "SEM BLOCO"
            if use_sg:
                sn = _norm_key(row.get("setor"))
                sn_g = sn if sn else "SEM SETOR"
                key = (sn_g, bn, p)
                if raw_s or raw_b:
                    cell_pair_votes[key][(raw_s, raw_b)] += 1
            else:
                key = (bn, p)
                if raw_b:
                    cell_pair_votes[key][("", raw_b)] += 1
            for pct_val in cell_values:
                ratio = max(0.0, min(1.0, float(pct_val) / 100.0))
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
            "origem": "mapa_controle_ambiente",
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
                "rdos_resumo": {
                    "aprovados": 0,
                    "pendentes": 0,
                    "sem_rdo": 0,
                    "pendentes_rdos_count": 0,
                },
                "ultimos_dias_calendario": [],
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

        # Calcula resumo diário com uma consulta agregada (evita N queries por dia).
        resumo_por_data = {
            row["date"]: {
                "total": int(row.get("n_total") or 0),
                "max_ap": int(row.get("n_aprovados") or 0),
            }
            for row in diaries_qs.values("date").annotate(
                n_total=Count("id"),
                n_aprovados=Count("id", filter=Q(status=DiaryStatus.APROVADO)),
            )
        }
        dias_periodo = max(1, (d2 - d1).days + 1)
        rdos_aprovados_dias = 0
        rdos_pendentes_dias = 0
        for info in resumo_por_data.values():
            if info["max_ap"] > 0:
                rdos_aprovados_dias += 1
            elif info["total"] > 0:
                rdos_pendentes_dias += 1
        rdos_sem = max(0, dias_periodo - rdos_aprovados_dias - rdos_pendentes_dias)

        pendentes_rdos_count = diaries_qs.filter(
            status=DiaryStatus.AGUARDANDO_APROVACAO_GESTOR,
        ).count()

        # Calendário “últimos dias”: do mais recente ao mais antigo, até hoje (local), dentro do período.
        data_fim_real = min(d2, timezone.localdate())
        data_inicio_real = d1
        ultimos_dias_calendario: list[dict[str, Any]] = []
        if data_fim_real >= data_inicio_real:
            by_date: dict[date, list[ConstructionDiary]] = defaultdict(list)
            for row in diaries_qs.filter(
                date__gte=data_inicio_real,
                date__lte=data_fim_real,
            ).order_by("date", "-created_at"):
                by_date[row.date].append(row)

            all_diary_ids: list[int] = []
            for lst in by_date.values():
                all_diary_ids.extend(d.id for d in lst)

            ocorrencias_por_rdo: dict[int, int] = {}
            if all_diary_ids:
                ocorrencias_por_rdo = dict(
                    DiaryOccurrence.objects.filter(diary_id__in=all_diary_ids)
                    .values("diary_id")
                    .annotate(n=Count("id"))
                    .values_list("diary_id", "n")
                )

            delta = (data_fim_real - data_inicio_real).days
            for i in range(delta + 1):
                dia = data_fim_real - timedelta(days=i)
                day_list = by_date.get(dia, [])
                if not day_list:
                    ultimos_dias_calendario.append(
                        {
                            "data": dia,
                            "tem_rdo": False,
                            "report_number": None,
                            "status": None,
                            "ocorrencias": 0,
                            "responsavel": None,
                        }
                    )
                else:
                    primary = next(
                        (x for x in day_list if x.status == DiaryStatus.APROVADO),
                        day_list[0],
                    )
                    occ_n = sum(ocorrencias_por_rdo.get(x.id, 0) for x in day_list)
                    resp = (
                        (primary.inspection_responsible or primary.production_responsible or "").strip()
                        or None
                    )
                    ultimos_dias_calendario.append(
                        {
                            "data": dia,
                            "tem_rdo": True,
                            "report_number": primary.report_number,
                            "status": primary.status,
                            "ocorrencias": occ_n,
                            "responsavel": resp,
                        }
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
        taxa_dias_com_ocorrencia = round((dias_com_ocorrencia / dias_periodo) * 100.0, 1)

        tags_qs = (
            OccurrenceTag.objects.filter(occurrences__in=occ_qs)
            .annotate(n=Count("occurrences", filter=Q(occurrences__in=occ_qs), distinct=True))
            .order_by("-n", "name")[:12]
        )
        tags_top = [
            {"id": t.id, "nome": t.name, "cor": t.color or "#64748b", "total": int(t.n or 0)}
            for t in tags_qs
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
            "rdos_resumo": {
                "aprovados": rdos_aprovados_dias,
                "pendentes": rdos_pendentes_dias,
                "sem_rdo": rdos_sem,
                "pendentes_rdos_count": pendentes_rdos_count,
            },
            "ultimos_dias_calendario": ultimos_dias_calendario,
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

        pct_raw = kc.get("percentual_medio")
        pct = float(pct_raw) if pct_raw is not None else 0.0
        atrasados = int(ks.get("atrasados") or 0)
        occ = int(kd.get("ocorrencias_no_periodo") or 0)
        occ_crit = int(pr.get("p1_critica") or kd.get("ocorrencias_criticas_no_periodo") or 0)

        sinais = 0
        motivos = []

        # Execução física: desvio vs avanço esperado no tempo.
        # mapa_obras.Obra não tem datas; usam-se core.Project.start_date / end_date via obra.project.
        obra = self.obra
        project = getattr(obra, "project", None)
        data_inicio = getattr(project, "start_date", None) if project else None
        data_fim = getattr(project, "end_date", None) if project else None
        hoje = date.today()

        usou_janela_temporal = False
        if (
            project is not None
            and data_inicio is not None
            and data_fim is not None
            and data_fim > data_inicio
        ):
            duracao_total = (data_fim - data_inicio).days
            if duracao_total > 0:
                decorrido = (hoje - data_inicio).days
                pct_tempo = max(0.0, min(1.0, decorrido / float(duracao_total))) * 100.0
                avanco_esperado = pct_tempo
                desvio = pct - avanco_esperado
                usou_janela_temporal = True

                if desvio < -20:
                    sinais += 2
                    motivos.append(
                        f"Execução muito abaixo do esperado ({pct:.1f}% real vs {avanco_esperado:.1f}% esperado)"
                    )
                elif desvio < -5:
                    sinais += 1
                    motivos.append(
                        f"Execução levemente abaixo do esperado ({pct:.1f}% real vs {avanco_esperado:.1f}% esperado)"
                    )

        if not usou_janela_temporal:
            if pct < 35:
                sinais += 2
                motivos.append("Execução física baixa (sem datas de prazo cadastradas)")
            elif pct < 55:
                sinais += 1
                motivos.append("Execução física requer atenção (sem datas de prazo cadastradas)")

        if atrasados >= 15:
            sinais += 2
            motivos.append("Muitos itens de suprimento atrasados")
        elif atrasados >= 6:
            sinais += 1
            motivos.append("Pressão na fila de suprimentos")

        if occ_crit >= 3:
            sinais += 2
            motivos.append("Ocorrências críticas recorrentes no diário")
        elif occ_crit >= 1:
            sinais += 1
            motivos.append("Há ocorrência crítica no período")
        elif occ >= 12:
            sinais += 1
            motivos.append("Volume alto de ocorrências no diário")

        if sinais <= 1:
            nivel = "ok"
            rotulo = "Obra dentro do previsto"
        elif sinais <= 3:
            nivel = "atencao"
            rotulo = "Obra em atenção"
        else:
            nivel = "risco"
            rotulo = "Obra com risco de atraso ou pressão operacional"

        return {"nivel": nivel, "rotulo": rotulo, "motivos": motivos, "sinais": sinais}
