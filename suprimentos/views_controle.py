import json
import os
import re
import tempfile
import unicodedata
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Avg, Q, Sum

from accounts.decorators import require_group
from accounts.groups import GRUPOS
from mapa_obras.models import Obra
from mapa_obras.contexto_obra import resolve_obra_context
from mapa_obras.views import _user_can_access_obra
from suprimentos.models import ImportacaoMapaServico, ItemMapaServico
from suprimentos.services.mapa_controle_viewmodel import AmbienteProvider, LegacyObraProvider
from suprimentos.services.mapa_controle_service import MapaControleFilters, MapaControleService

_PLACEHOLDER_ROW_KEYS = frozenset(
    {
        "sem valor",
        "sem bloco",
        "sem pav.",
        "sem pavimento",
        "sem apto",
        "sem setor",
    }
)
# Só placeholders genéricos do import ("Linha 1", "linha 2") — não nomes reais como "linha 1 bloco".
_LINHA_ROW_PLACEHOLDER_RE = re.compile(r"^linha\s+\d+\s*$", re.IGNORECASE)


def _matrix_row_drillable(row_key: str) -> bool:
    key = str(row_key or "").strip()
    if not key:
        return False
    low = key.lower()
    if low in _PLACEHOLDER_ROW_KEYS:
        return False
    if _LINHA_ROW_PLACEHOLDER_RE.match(key):
        return False
    return True


def _resolve_obra_for_request(request):
    return resolve_obra_context(request)


def _layer_aggregates(queryset, group_field: str):
    return list(
        queryset.values(group_field)
        .annotate(
            total=Count("id"),
            progresso=Avg("status_percentual"),
            custo_total=Sum("custo"),
            concluidos=Count("id", filter=Q(status_percentual__gte=1) | Q(status_texto__icontains="conclu")),
            em_andamento=Count(
                "id",
                filter=Q(status_percentual__gt=0, status_percentual__lt=1)
                | Q(status_texto__icontains="exec")
                | Q(status_texto__icontains="parcial"),
            ),
            nao_iniciados=Count(
                "id",
                filter=Q(status_percentual__lte=0)
                | Q(status_texto__icontains="nao")
                | Q(status_texto__icontains="não")
                | Q(status_texto__icontains="pend"),
            ),
        )
        .order_by(group_field)
    )


def _extract_first_matrix_rows_from_layout(layout: dict) -> tuple[list[list], dict]:
    if not isinstance(layout, dict):
        return [], {}
    sections = layout.get("sections")
    if not isinstance(sections, list):
        return [], {}
    for section in sections:
        if not isinstance(section, dict):
            continue
        data = section.get("data") if isinstance(section.get("data"), dict) else {}
        rows = data.get("rows")
        if not isinstance(rows, list) or not rows:
            continue
        out = []
        for row in rows:
            if isinstance(row, list):
                out.append([str(cell or "") for cell in row])
            else:
                out.append([str(row or "")])
        import_meta = data.get("importMeta") if isinstance(data.get("importMeta"), dict) else {}
        return _upgrade_manual_flat_layout(out, import_meta)
    return [], {}


def _upgrade_manual_flat_layout(rows: list[list], meta: dict) -> tuple[list[list], dict]:
    """
    Mapas manuais antigos tinham só uma coluna de eixo (Bloco/local).
    Promove para BLOCO → PAVIMENTO → APTO para permitir drill-down intuitivo.
    """
    if not rows or not isinstance(meta, dict):
        return rows, meta
    if meta.get("strategy") != "manual_template":
        return rows, meta
    axis_cols = meta.get("axis_cols_interpreted") if isinstance(meta.get("axis_cols_interpreted"), list) else []
    if len(axis_cols) > 1:
        return rows, meta

    header = rows[0] if isinstance(rows[0], list) else []
    activity_headers: list[str] = []
    for idx in range(1, len(header)):
        label = str(header[idx] or "").strip()
        if _is_total_header_label(label):
            continue
        activity_headers.append(label or f"Atividade {len(activity_headers) + 1}")

    new_header = ["BLOCO", "PAVIMENTO", "APTO"] + activity_headers + ["Total"]
    new_rows: list[list] = [new_header]
    for old in rows[1:]:
        if not isinstance(old, list):
            continue
        bloco_label = str(old[0] if len(old) else "").strip()
        activities: list[str] = []
        total_cell = ""
        for idx in range(1, len(old)):
            if idx < len(header) and _is_total_header_label(str(header[idx] or "")):
                total_cell = str(old[idx] or "")
                continue
            activities.append(str(old[idx] if idx < len(old) else ""))
        while len(activities) < len(activity_headers):
            activities.append("")
        new_rows.append([bloco_label, "", ""] + activities[: len(activity_headers)] + [total_cell])

    act_cols = list(range(3, 3 + len(activity_headers)))
    new_meta = {
        **meta,
        "axis_cols_interpreted": [0, 1, 2],
        "axis_headers_interpreted": ["BLOCO", "PAVIMENTO", "APTO"],
        "activity_cols_interpreted": act_cols,
        "row_axis_key": "bloco",
    }
    return new_rows, new_meta


def _normalize_ambiente_layout(layout: dict) -> dict:
    """Aplica upgrades de schema no layout (ex.: manual 1 coluna → hierarquia BLOCO/PAV/APTO)."""
    if not isinstance(layout, dict):
        return layout
    sections = layout.get("sections")
    if not isinstance(sections, list):
        return layout
    for section in sections:
        if not isinstance(section, dict):
            continue
        if str(section.get("kind") or "").strip() not in {"matrix_table", "table"}:
            continue
        data = section.get("data") if isinstance(section.get("data"), dict) else {}
        rows = data.get("rows")
        if not isinstance(rows, list) or not rows:
            continue
        meta = data.get("importMeta") if isinstance(data.get("importMeta"), dict) else {}
        normalized_rows, normalized_meta = _upgrade_manual_flat_layout(
            [
                [str(cell or "") for cell in row] if isinstance(row, list) else [str(row or "")]
                for row in rows
            ],
            meta,
        )
        section.setdefault("data", {})
        section["data"]["rows"] = normalized_rows
        section["data"]["importMeta"] = normalized_meta
    return layout


def _parse_matrix_pct(value):
    """Vazio = sem lançamento (None na grade). \"-\" = N/A. Número/0% explícito = valor."""
    from suprimentos.services.mapa_controle_viewmodel import _cell_pct_for_average, _is_pct_not_applicable

    if _is_pct_not_applicable(value):
        return None
    if not str(value or "").strip():
        return None
    return _cell_pct_for_average(value)


def _is_total_header_label(value: str) -> bool:
    token = str(value or "").strip().upper()
    if not token:
        return False
    return token == "TOTAL" or token == "TOTAL GERAL" or token.startswith("TOTAL")


def _matrix_header_is_axis_label(value: str) -> bool:
    token = str(value or "").strip().upper()
    if not token:
        return False
    if "SETOR" in token or "REGIAO" in token:
        return True
    if "BLOCO" in token or "LOCAL" in token or "TORRE" in token:
        return True
    if "PAV" in token or "ANDAR" in token or "NIVEL" in token:
        return True
    if "APTO" in token or "UNIDADE" in token:
        return True
    return False


def _normalize_meta_col_indices(values) -> list[int]:
    out = []
    if not isinstance(values, list):
        return out
    for item in values:
        try:
            idx = int(item)
        except (TypeError, ValueError):
            continue
        if idx < 0:
            continue
        out.append(idx)
    seen = set()
    dedup = []
    for idx in out:
        if idx in seen:
            continue
        seen.add(idx)
        dedup.append(idx)
    return dedup


def _build_matrix_payload_from_rows(rows: list[list[str]], matrix_meta: dict | None = None) -> tuple[dict, dict]:
    if not rows or not isinstance(rows[0], list):
        return (
            {"atividades": [], "rows": [], "totais": [], "mode": "bloco", "header_first_col": "Bloco"},
            {"total_itens": 0, "percentual_medio": 0.0, "concluidos": 0, "em_andamento": 0, "nao_iniciados": 0},
        )

    matrix_meta = matrix_meta if isinstance(matrix_meta, dict) else {}
    header = rows[0]
    total_col_idx = matrix_meta.get("total_col_interpreted")
    if not isinstance(total_col_idx, int) or total_col_idx < 0 or total_col_idx >= len(header):
        total_col_idx = None
        for i in range(len(header) - 1, -1, -1):
            if _is_total_header_label(header[i]):
                total_col_idx = i
                break

    axis_col_indices = _normalize_meta_col_indices(matrix_meta.get("axis_cols_interpreted"))
    axis_col_indices = [i for i in axis_col_indices if i < len(header)]
    axis_headers = [str(header[i] or "").strip() or f"Eixo {idx + 1}" for idx, i in enumerate(axis_col_indices)]
    if not axis_col_indices and isinstance(matrix_meta.get("axis_headers_interpreted"), list):
        wanted = [str(v or "").strip().upper() for v in matrix_meta.get("axis_headers_interpreted") if str(v or "").strip()]
        for idx, raw in enumerate(header):
            if not wanted:
                break
            token = str(raw or "").strip().upper()
            if token and token == wanted[0]:
                axis_col_indices.append(idx)
                axis_headers.append(str(raw or "").strip() or f"Eixo {len(axis_col_indices)}")
                wanted.pop(0)

    activity_col_indices = _normalize_meta_col_indices(matrix_meta.get("activity_cols_interpreted"))
    activity_col_indices = [i for i in activity_col_indices if i < len(header)]
    axis_set = set(axis_col_indices)
    if axis_col_indices:
        if not activity_col_indices:
            activity_col_indices = [i for i in range(len(header)) if i not in axis_set and i != total_col_idx]
    else:
        if not activity_col_indices:
            activity_col_indices = [i for i in range(1, len(header)) if i != total_col_idx]

    if not activity_col_indices:
        activity_col_indices = [i for i in range(len(header)) if i != total_col_idx]

    activity_col_indices = [
        i
        for i in activity_col_indices
        if i != total_col_idx and not _matrix_header_is_axis_label(str(header[i] or ""))
    ]

    if axis_headers:
        header_first_col = " / ".join(axis_headers)[:120]
    else:
        header_first_col = str(header[0] or "Bloco").strip() or "Bloco"

    row_axis_cols = _normalize_meta_col_indices(matrix_meta.get("row_axis_cols_interpreted"))
    row_axis_cols = [i for i in row_axis_cols if i < len(header)]
    if not row_axis_cols:
        row_axis_cols = list(axis_col_indices)

    data_col_indices = activity_col_indices
    atividade_labels = [str(header[i] or "").strip() or f"Atividade {idx + 1}" for idx, i in enumerate(data_col_indices)]
    atividade_count = len(data_col_indices)
    group_map_raw = matrix_meta.get("activity_group_map") if isinstance(matrix_meta.get("activity_group_map"), dict) else {}
    group_map_norm = {str(k or "").strip().upper(): str(v or "").strip() for k, v in group_map_raw.items()}
    atividade_grupos = {}
    for label in atividade_labels:
        key = str(label or "").strip().upper()
        if not key:
            continue
        grupo = group_map_norm.get(key) or ""
        if grupo:
            atividade_grupos[label] = grupo

    matrix_rows = []
    col_values: list[list[float]] = [[] for _ in range(atividade_count)]
    all_values: list[float] = []

    for row_idx, row in enumerate(rows[1:]):
        if not isinstance(row, list):
            continue
        if row_axis_cols:
            axis_values = []
            for idx in row_axis_cols:
                axis_values.append(str((row[idx] if len(row) > idx else "") or "").strip())
            row_label = " / ".join([v for v in axis_values if v]).strip()
            if not row_label:
                row_label = str((row[row_axis_cols[0]] if len(row) > row_axis_cols[0] else "") or "").strip()
        else:
            row_label = str((row[0] if row else "") or "").strip()
        row_label = row_label or f"Linha {row_idx + 1}"
        cells = []
        row_values: list[float] = []
        for pos, atividade in enumerate(atividade_labels):
            col_idx = data_col_indices[pos]
            raw_cell = row[col_idx] if len(row) > col_idx else ""
            raw_txt = str(raw_cell or "").strip()
            pct = _parse_matrix_pct(raw_cell)
            if raw_txt and pct is not None:
                pct_num = float(pct)
                row_values.append(pct_num)
            if pct is not None:
                col_values[pos].append(float(pct))
                all_values.append(float(pct))
            cells.append({"atividade": atividade, "pct": pct, "raw": raw_txt})

        raw_total = ""
        if total_col_idx is not None and len(row) > total_col_idx:
            raw_total = row[total_col_idx]
        if row_values:
            total = round(sum(row_values) / len(row_values), 2)
        else:
            total = _parse_matrix_pct(raw_total)
            if total is not None:
                total = round(float(total), 2)
        matrix_rows.append(
            {
                "row_key": row_label,
                "row_label": row_label,
                "row_drillable": _matrix_row_drillable(row_label),
                "cells": cells,
                "total": total,
            }
        )

    totais = []
    for col_idx, atividade in enumerate(atividade_labels):
        vals = col_values[col_idx]
        if not vals:
            totais.append({"atividade": atividade, "pct": None})
            continue
        pct = round(sum(vals) / len(vals), 2)
        totais.append({"atividade": atividade, "pct": pct})

    if all_values:
        media_fmt = round(sum(all_values) / len(all_values), 2)
    else:
        media_fmt = 0.0

    kpis = {
        "total_itens": len(all_values),
        "percentual_medio": media_fmt,
        "concluidos": sum(1 for v in all_values if v >= 99.5),
        "em_andamento": sum(1 for v in all_values if 0 < v < 99.5),
        "nao_iniciados": sum(1 for v in all_values if v <= 0),
    }
    from suprimentos.services.mapa_controle_viewmodel import _grand_total_from_matrix_rows

    matrix = {
        "atividades": atividade_labels,
        "atividade_grupos": atividade_grupos,
        "rows": matrix_rows,
        "totais": totais,
        "total_geral": _grand_total_from_matrix_rows(matrix_rows),
        "mode": "bloco",
        "header_first_col": header_first_col,
    }
    return matrix, kpis


def _build_layers_navigation(raw_qs, selected: dict) -> dict:
    """
    Opções dos chips de camada: lista completa de irmãos no recorte geográfico.
    Não aplica busca nem status — assim ao escolher um bloco não somem os outros (A/B/C)
    nem os setores irmãos.

    Quando há coluna (``atividade``) no recorte, blocos/pavimentos usam só essa atividade
    e o progresso por bloco segue a mesma regra da matriz (média por pavimento).
    """
    layers: dict[str, list] = {"setores": [], "blocos": [], "pavimentos": [], "aptos": []}
    layers["setores"] = _layer_aggregates(raw_qs, "setor")
    if not (selected.get("setor") or "").strip():
        return layers
    qs_bl = raw_qs.filter(setor=selected["setor"])
    ativ_nav = (selected.get("atividade") or "").strip()
    if ativ_nav:
        layers["blocos"] = _layer_blocos_nav_hier_por_pavimento(
            qs_bl.filter(atividade__iexact=ativ_nav)
        )
    else:
        layers["blocos"] = _layer_aggregates(qs_bl, "bloco")
    if not (selected.get("bloco") or "").strip():
        return layers
    qs_pav = qs_bl.filter(bloco=selected["bloco"])
    if ativ_nav:
        qs_pav = qs_pav.filter(atividade__iexact=ativ_nav)
    layers["pavimentos"] = _layer_aggregates(qs_pav, "pavimento")
    if not (selected.get("pavimento") or "").strip():
        return layers
    if _setor_e_area_comum((selected.get("setor") or "")):
        # ÁREA COMUM: Bloco → Pavimento → serviços (não há camada de unidade/apto).
        layers["aptos"] = []
        return layers
    qs_ap = qs_pav.filter(pavimento=selected["pavimento"])
    layers["aptos"] = _layer_aggregates(qs_ap, "apto")
    return layers


def _build_filters_from_request(request):
    try:
        limit = int(request.GET.get("limit", 200) or 200)
    except ValueError:
        limit = 200
    try:
        offset = int(request.GET.get("offset", 0) or 0)
    except ValueError:
        offset = 0
    return MapaControleFilters(
        categoria=(request.GET.get("categoria") or "").strip(),
        local_id=(request.GET.get("local") or "").strip(),
        prioridade=(request.GET.get("prioridade") or "").strip(),
        status=(request.GET.get("status") or "").strip(),
        search=(request.GET.get("search") or "").strip(),
        limit=limit,
        offset=max(0, offset),
    )


def _parse_json_body(request):
    try:
        body = (request.body or b"").decode("utf-8")
        return json.loads(body or "{}")
    except Exception:
        return {}


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
    if "conclu" in txt or "final" in txt or "entreg" in txt:
        return 1.0
    if "exec" in txt or "andamento" in txt or "parcial" in txt:
        return 0.5
    if "nao" in txt or "não" in txt or "pend" in txt or "aguard" in txt:
        return 0.0
    return None


def _status_bucket_from_ratio(ratio: float | None) -> str:
    if ratio is None:
        return "indefinido"
    if ratio >= 1.0:
        return "concluido"
    if ratio <= 0.0:
        return "nao_iniciado"
    return "em_andamento"


def _norm_key(value: object) -> str:
    text = (str(value or "")).strip().upper()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("ASCII")
    return " ".join(text.split())


def _compact_layer_key(value: object) -> str:
    """Normaliza rótulos de camada para comparação hierárquica leve."""
    norm = _norm_key(value)
    if not norm:
        return ""
    return "".join(ch for ch in norm if ch.isalnum())


def _is_parent_block_label(parent: str, child: str) -> bool:
    """
    Detecta padrão pai->filho em blocos (ex.: A -> A1, TORRE A -> TORRE A1).
    Só considera pai sem dígitos para não confundir pares válidos como Q1/Q10.
    """
    p = _compact_layer_key(parent)
    c = _compact_layer_key(child)
    if not p or not c or p == c:
        return False
    if any(ch.isdigit() for ch in p):
        return False
    if len(c) <= len(p) or not c.startswith(p):
        return False
    return c[len(p)].isdigit()


def _parent_block_rows_to_hide_by_similarity(
    rows_sorted: list[str],
    atividades: list[str],
    agg: dict[tuple[str, str], dict],
) -> set[str]:
    """
    Remove rótulo pai apenas quando ele aparenta ser um agregado dos filhos.

    Regra híbrida (ainda conservadora):
    - pai textual (sem dígitos) com >=2 filhos (A -> A1/A2);
    - pai e filhos com sobreposição de atividades;
    - esconde quando houver forte indício de agregação por:
      (a) alta similaridade de % com a média dos filhos, OU
      (b) pai muito mais esparso que os filhos (linha-resumo típica).
    """
    rows = [str(r or "").strip() for r in rows_sorted if str(r or "").strip()]
    to_hide: set[str] = set()
    if not rows or not atividades or not agg:
        return to_hide

    def _row_vector(label: str) -> dict[str, float]:
        out: dict[str, float] = {}
        for atividade in atividades:
            data = agg.get((label, atividade))
            if not data or not data.get("count"):
                continue
            out[atividade] = (float(data.get("sum") or 0.0) / float(data.get("count") or 1.0)) * 100.0
        return out

    def _is_short_alpha_parent(label: str) -> bool:
        compact = _compact_layer_key(label)
        if not compact:
            return False
        if any(ch.isdigit() for ch in compact):
            return False
        return len(compact) <= 2

    for parent in rows:
        children = [child for child in rows if child != parent and _is_parent_block_label(parent, child)]
        if len(children) < 1:
            continue

        parent_vec = _row_vector(parent)
        if not parent_vec:
            continue

        diffs = []
        overlap = 0
        for atividade, parent_pct in parent_vec.items():
            child_vals = []
            for child in children:
                data = agg.get((child, atividade))
                if not data or not data.get("count"):
                    continue
                child_vals.append((float(data.get("sum") or 0.0) / float(data.get("count") or 1.0)) * 100.0)
            if not child_vals:
                continue
            overlap += 1
            child_mean = sum(child_vals) / len(child_vals)
            diffs.append(abs(parent_pct - child_mean))

        if not diffs:
            continue

        parent_density = len(parent_vec)
        child_densities = [len(_row_vector(child)) for child in children]
        child_density_mean = (sum(child_densities) / len(child_densities)) if child_densities else 0.0
        sparse_parent = parent_density <= max(2, int(round(child_density_mean * 0.35)))

        mean_abs_diff = sum(diffs) / len(diffs)
        close_to_children = overlap >= 3 and mean_abs_diff <= 3.5

        # Se houver sobreposição mínima e o pai estiver muito esparso, tende a ser linha-resumo.
        sparse_summary_like = overlap >= 1 and sparse_parent
        # Caso comum em importações: eixo curto (A/B/C) + filhos A1/A2...
        # Mesmo sem colunas sobrepostas, o pai costuma ser agregador estrutural.
        structural_parent_like = _is_short_alpha_parent(parent) and parent_density <= 1

        if close_to_children or sparse_summary_like or structural_parent_like:
            to_hide.add(parent)

    return to_hide


def _setor_e_area_comum(setor: str) -> bool:
    """ÁREA COMUM: Bloco → Pavimento → serviços (sem camada de apartamento/unidade)."""
    if not (setor or "").strip():
        return False
    return _norm_key(setor) == "AREA COMUM"


def _parse_grid_pct_clicado(request) -> int | None:
    """% exibido na célula ao clicar — só para exibição no detalhe (confiança do utilizador)."""
    raw = (request.GET.get("grid_pct") or "").strip()
    if not raw:
        return None
    try:
        v = int(raw, 10)
    except ValueError:
        return None
    if 0 <= v <= 100:
        return v
    return None


def _resolve_matrix_mode(requested: str, selected: dict) -> str:
    """Define granularidade das linhas da matriz (bloco / pavimento / apto).

    Com `matrix_mode` omitido na URL, infere pelo recorte ativo: só setor → blocos;
    setor+bloco → pavimentos; setor+bloco+pavimento (HABITAÇÃO) → unidades.
    Em ÁREA COMUM (sem apto), com bloco no recorte o modo é sempre pavimento.
    Valores explícitos na query são respeitados quando compatíveis com os filtros.
    """
    r = (requested or "").strip().lower()
    if r not in ("bloco", "pavimento", "apto"):
        r = ""

    setor = (selected.get("setor") or "").strip()
    bloco = (selected.get("bloco") or "").strip()
    pavimento = (selected.get("pavimento") or "").strip()

    if _setor_e_area_comum(setor):
        # Sem camada de unidade: no máximo linhas por pavimento (nunca apto).
        if r == "apto":
            r = "pavimento"
        # Recorte com bloco → sempre grade por pavimento (1…N linhas por pavimento
        # do bloco), mesmo se matrix_mode=bloco ainda estiver na URL.
        if bloco:
            return "pavimento"
        if r == "pavimento" and not bloco:
            return "bloco"
        if r == "pavimento":
            return "pavimento"
        if r == "bloco":
            return "bloco"
        return "bloco"

    # O recorte ativo manda na camada efetiva. Evita matrix_mode residual
    # gerar contexto errado de edição/exclusão ao descer níveis.
    if bloco and pavimento:
        return "apto"
    if bloco:
        return "pavimento"
    if r in ("apto", "pavimento", "bloco"):
        return "bloco"
    if setor:
        return "bloco"
    return "bloco"


def _row_field_for_matrix_mode(mode: str) -> str:
    return {"bloco": "bloco", "pavimento": "pavimento", "apto": "apto"}.get(mode, "bloco")


def _default_label_for_row_field(row_field: str) -> str:
    return {
        "bloco": "SEM BLOCO",
        "pavimento": "SEM PAVIMENTO",
        "apto": "SEM APTO",
    }.get(row_field, "SEM REGISTRO")


def _mean_ratio_equal_weight_groups(
    items: list,
    group_key_fn,
) -> float | None:
    """Média da média por grupo (cada grupo pesa igual), ignorando itens sem ratio."""
    by_g: dict[str, list[float]] = {}
    for item in items:
        ratio = _status_to_ratio(item)
        if ratio is None:
            continue
        g = group_key_fn(item)
        by_g.setdefault(g, []).append(ratio)
    inner = [sum(vals) / len(vals) for vals in by_g.values() if vals]
    if not inner:
        return None
    return sum(inner) / len(inner)


def _mean_ratio_equal_weight_blocos_then_pavimento(items: list) -> float | None:
    """Média por bloco (cada bloco pesa igual); dentro de cada bloco, média por pavimento."""
    by_bloco: dict[str, list] = {}
    for it in items:
        b = (str(getattr(it, "bloco", None) or "").strip() or "SEM BLOCO")
        by_bloco.setdefault(b, []).append(it)
    bloco_means: list[float] = []
    for bloc_items in by_bloco.values():
        m = _mean_ratio_equal_weight_groups(
            bloc_items,
            lambda it: (str(getattr(it, "pavimento", None) or "").strip() or "SEM PAVIMENTO"),
        )
        if m is not None:
            bloco_means.append(m)
    if not bloco_means:
        return None
    return sum(bloco_means) / len(bloco_means)


def _layer_blocos_nav_hier_por_pavimento(qs) -> list[dict]:
    """
    Mesmo contrato que ``_layer_aggregates(..., 'bloco')``, com ``progresso`` em 0–1
    alinhado à célula da matriz (média por pavimento dentro do bloco).
    """
    items = list(
        qs.only("bloco", "pavimento", "status_percentual", "status_texto").order_by("bloco")
    )
    by_bloco: dict[str, list] = {}
    for it in items:
        b = (str(it.bloco or "").strip() or "SEM BLOCO")
        by_bloco.setdefault(b, []).append(it)
    rows: list[dict] = []
    for b in sorted(by_bloco.keys()):
        bloc_items = by_bloco[b]
        hier = _mean_ratio_equal_weight_groups(
            bloc_items,
            lambda it: (str(getattr(it, "pavimento", None) or "").strip() or "SEM PAVIMENTO"),
        )
        total = len(bloc_items)
        concluidos = em_andamento = nao_iniciados = 0
        for item in bloc_items:
            ratio = _status_to_ratio(item)
            status_txt = (item.status_texto or "").lower()
            if ratio is not None:
                if ratio >= 1.0:
                    concluidos += 1
                elif ratio <= 0.0:
                    nao_iniciados += 1
                else:
                    em_andamento += 1
            elif "conclu" in status_txt:
                concluidos += 1
            elif "exec" in status_txt or "parcial" in status_txt:
                em_andamento += 1
            else:
                nao_iniciados += 1
        rows.append(
            {
                "bloco": b if b != "SEM BLOCO" else None,
                "total": total,
                "progresso": hier,
                "custo_total": None,
                "concluidos": concluidos,
                "em_andamento": em_andamento,
                "nao_iniciados": nao_iniciados,
            }
        )
    return rows


def _build_matrix_grid(
    matrix_scope_qs,
    row_field: str,
    atividades_max: int = 36,
    rows_max: int = 60,
) -> dict:
    """Agrega percentuais em uma grade (linha x atividade), ex.: bloco×atividade ou pavimento×atividade.

    Em linhas por **bloco**, cada célula usa média por **pavimento** e depois média entre pavimentos
    (cada pavimento pesa igual), alinhado à linha Total da grade por pavimento e ao detalhe da célula.
    """
    default_row = _default_label_for_row_field(row_field)
    only_fields = [row_field, "atividade", "status_percentual", "status_texto"]
    if row_field == "bloco":
        only_fields.append("pavimento")
    matrix_items = list(matrix_scope_qs.only(*only_fields).order_by(row_field, "atividade"))
    agg: dict[tuple[str, str], dict] = {}
    rows_set: set[str] = set()
    atividades_set: set[str] = set()
    for item in matrix_items:
        raw = getattr(item, row_field, None)
        row_val = (str(raw).strip() if raw is not None else "") or default_row
        atividade = (item.atividade or "SEM ATIVIDADE").strip() or "SEM ATIVIDADE"
        # Sempre registra linha e coluna; só agrega % quando há ratio interpretável.
        # Antes: `continue` quando ratio era None — blocos inteiros sumiam da matriz.
        rows_set.add(row_val)
        atividades_set.add(atividade)
        ratio = _status_to_ratio(item)
        if ratio is None:
            continue
        key = (row_val, atividade)
        if row_field == "bloco":
            pav_val = (str(getattr(item, "pavimento", None) or "").strip() or "SEM PAVIMENTO")
            if key not in agg:
                agg[key] = {"by_pav": {}}
            bp = agg[key]["by_pav"]
            if pav_val not in bp:
                bp[pav_val] = {"sum": 0.0, "count": 0}
            bp[pav_val]["sum"] += ratio
            bp[pav_val]["count"] += 1
        else:
            if key not in agg:
                agg[key] = {"sum": 0.0, "count": 0}
            agg[key]["sum"] += ratio
            agg[key]["count"] += 1

    if row_field == "bloco":
        flat: dict[tuple[str, str], dict] = {}
        for key, data in agg.items():
            by_pav = data.get("by_pav") or {}
            inner_means = [
                b["sum"] / b["count"] for b in by_pav.values() if b.get("count", 0) > 0
            ]
            if inner_means:
                m = sum(inner_means) / len(inner_means)
                flat[key] = {"sum": m, "count": 1}
        agg = flat

    atividades = sorted(atividades_set)[:atividades_max]
    rows_sorted = sorted(rows_set)
    if row_field == "bloco":
        hide_rows = _parent_block_rows_to_hide_by_similarity(rows_sorted, atividades, agg)
        if hide_rows:
            rows_sorted = [row for row in rows_sorted if row not in hide_rows]
    rows_sorted = rows_sorted[:rows_max]
    rows_out = []
    for row_val in rows_sorted:
        cells = []
        row_sum = 0.0
        row_count = 0
        for atividade in atividades:
            data = agg.get((row_val, atividade))
            if data and data["count"] > 0:
                pct = round((data["sum"] / data["count"]) * 100)
                row_sum += pct
                row_count += 1
                cells.append({"atividade": atividade, "pct": pct})
            else:
                cells.append({"atividade": atividade, "pct": None})
        total_pct = round(row_sum / row_count) if row_count else None
        rows_out.append(
            {
                "row_key": row_val,
                "row_label": row_val,
                "cells": cells,
                "total": total_pct,
            }
        )

    totais = []
    for atividade in atividades:
        col_values = []
        for row_val in rows_sorted:
            data = agg.get((row_val, atividade))
            if data and data["count"] > 0:
                col_values.append(round((data["sum"] / data["count"]) * 100))
        totais.append(
            {
                "atividade": atividade,
                "pct": round(sum(col_values) / len(col_values)) if col_values else None,
            }
        )

    return {"atividades": atividades, "rows": rows_out, "totais": totais}


def _build_confiabilidade_controle(total_itens: int, qualidade: dict) -> dict:
    if total_itens <= 0:
        return {"score": 0.0, "nivel": "sem_dados", "nivel_display": "Sem dados"}

    sem_bloco = qualidade.get("sem_bloco", 0)
    sem_pavimento = qualidade.get("sem_pavimento", 0)
    sem_apto = qualidade.get("sem_apto", 0)
    sem_pct = qualidade.get("sem_status_percentual", 0)
    sem_termino = qualidade.get("sem_data_termino", 0)

    penalidade = (
        (sem_bloco / total_itens) * 20
        + (sem_pavimento / total_itens) * 20
        + (sem_apto / total_itens) * 20
        + (sem_pct / total_itens) * 30
        + (sem_termino / total_itens) * 10
    )
    score = max(0.0, round(100 - penalidade, 2))
    if score >= 95:
        nivel = "excelente"
        nivel_display = "Excelente"
    elif score >= 85:
        nivel = "bom"
        nivel_display = "Bom"
    elif score >= 70:
        nivel = "atenção"
        nivel_display = "Atenção"
    else:
        nivel = "crítico"
        nivel_display = "Crítico"
    return {"score": score, "nivel": nivel, "nivel_display": nivel_display}


def _macro_pulse(kpis: dict, confiabilidade: dict, qualidade: dict) -> dict | None:
    """Uma linha de leitura rápida do escopo (correria) + opcional alerta de dados."""
    total = int(kpis.get("total_itens") or 0)
    if total <= 0:
        return {
            "headline": "Nenhum item neste recorte.",
            "sub": "Ajuste filtros, busca ou chips.",
            "tone": "neutral",
            "visible": True,
        }

    c = int(kpis.get("concluidos") or 0)
    e = int(kpis.get("em_andamento") or 0)
    n = int(kpis.get("nao_iniciados") or 0)
    pct_done = round(100 * c / total)
    sem_pct = int(qualidade.get("sem_status_percentual") or 0)
    nivel = (confiabilidade.get("nivel") or "").lower()
    score = confiabilidade.get("score")

    headline = (
        f"{total} itens no escopo · {pct_done}% concluídos · "
        f"{e} em andamento · {n} não iniciados"
    )

    sub_parts: list[str] = []
    if nivel in ("crítico", "atenção") and score is not None:
        sub_parts.append(
            f"Qualidade dos dados: {confiabilidade.get('nivel_display', nivel)} ({score}%)"
        )
    if sem_pct and (sem_pct / total) >= 0.08:
        sub_parts.append(f"{sem_pct} sem % tratável no escopo")

    share_nao_ini = n / total
    tone = "ok"
    if nivel == "crítico" or share_nao_ini > 0.5:
        tone = "bad"
    elif nivel == "atenção" or pct_done < 35 or share_nao_ini > 0.3:
        tone = "warn"

    sub = " · ".join(sub_parts) if sub_parts else None
    return {
        "headline": headline,
        "sub": sub,
        "tone": tone,
        "visible": bool(sub) or tone != "ok",
    }


@login_required
@require_group(GRUPOS.MAPA_CONTROLE)
@ensure_csrf_cookie
@cache_control(no_store=True, no_cache=True, must_revalidate=True, max_age=0)
def mapa_controle(request):
    ctx = _resolve_obra_for_request(request)
    obras, obra = ctx
    embed_mode = (request.GET.get("embed") or "").strip() == "1"
    ambiente_param = (request.GET.get("ambiente_id") or "").strip()
    ambiente_id_ctx = None
    grid_pct_clicado = _parse_grid_pct_clicado(request)
    selected = {
        "setor": (request.GET.get("setor") or "").strip(),
        "bloco": (request.GET.get("bloco") or "").strip(),
        "pavimento": (request.GET.get("pavimento") or "").strip(),
        "apto": (request.GET.get("apto") or "").strip(),
        "atividade": (request.GET.get("atividade") or "").strip(),
        "status": (request.GET.get("status") or "").strip(),
        "search": (request.GET.get("search") or "").strip(),
        "quick_find": (request.GET.get("quick") or "").strip(),
        "matrix_mode": (request.GET.get("matrix_mode") or "").strip(),
        "column_group": (request.GET.get("column_group") or "").strip(),
    }
    view_ctx = None
    if obra and ambiente_param:
        try:
            ambiente_id = int(ambiente_param)
        except (TypeError, ValueError):
            ambiente_id = None
        if ambiente_id:
            ambiente_id_ctx = ambiente_id
            # No modo dedicado, mantém apenas pesquisa universal.
            selected["status"] = ""
            selected["quick_find"] = ""
            provider = AmbienteProvider(
                extract_first_matrix_rows_from_layout=_extract_first_matrix_rows_from_layout,
                build_matrix_payload_from_rows=_build_matrix_payload_from_rows,
            )
            view_ctx = provider.build(
                obra=obra,
                selected=selected,
                ambiente_id=ambiente_id,
            )
            if view_ctx is None:
                return render(
                    request,
                    "suprimentos/mapa_controle.html",
                    {
                        **ctx.to_template_context(),
                        "selected": selected,
                        "layers": {"setores": [], "blocos": [], "pavimentos": [], "aptos": []},
                        "itens_atividade": [],
                        "matrix": {"atividades": [], "rows": [], "totais": [], "mode": "bloco", "header_first_col": "Bloco"},
                        "kpis": {"total_itens": 0, "percentual_medio": 0.0, "concluidos": 0, "em_andamento": 0, "nao_iniciados": 0},
                        "qualidade": {"sem_bloco": 0, "sem_pavimento": 0, "sem_apto": 0, "sem_status_percentual": 0, "sem_data_termino": 0},
                        "confiabilidade": {"score": 0.0, "nivel": "sem_dados", "nivel_display": "Sem dados"},
                        "quick_match": None,
                        "importacao_info": None,
                        "focus_detail": None,
                        "matrix_context": None,
                        "coluna_filtrada_aviso": None,
                        "macro_pulse": None,
                        "matrix_stable_qs": "",
                        "is_area_comum": False,
                        "embed_mode": embed_mode,
                        "column_groups": [],
                        "matrix_all_atividades": [],
                        "column_group_selected": "",
                        "column_group_save_url": "",
                        "layer_nav": {"has_scope": False, "depth": 0, "root_url": "", "prev_url": "", "current_path": "Mapa geral", "breadcrumbs": []},
                        "matrix_cell_colors": {},
                        "erro_mapa_ambiente": "Ambiente de mapa não encontrado para esta obra.",
                    },
                    status=404,
                )

    if view_ctx is None:
        provider = LegacyObraProvider(
            status_to_ratio=_status_to_ratio,
            setor_e_area_comum=_setor_e_area_comum,
            build_layers_navigation=_build_layers_navigation,
            resolve_matrix_mode=_resolve_matrix_mode,
            row_field_for_matrix_mode=_row_field_for_matrix_mode,
            build_matrix_grid=_build_matrix_grid,
            status_bucket_from_ratio=_status_bucket_from_ratio,
            norm_key=_norm_key,
            mean_ratio_equal_weight_groups=_mean_ratio_equal_weight_groups,
            mean_ratio_equal_weight_blocos_then_pavimento=_mean_ratio_equal_weight_blocos_then_pavimento,
            build_confiabilidade_controle=_build_confiabilidade_controle,
            macro_pulse=_macro_pulse,
        )
        view_ctx = provider.build(
            request=request,
            obra=obra,
            selected=selected,
            grid_pct_clicado=grid_pct_clicado,
        )

    return render(
        request,
        "suprimentos/mapa_controle.html",
        {
            **ctx.to_template_context(),
            "selected": view_ctx["selected"],
            "layers": view_ctx["layers"],
            "itens_atividade": view_ctx["itens_atividade"],
            "matrix": view_ctx["matrix"],
            "kpis": view_ctx["kpis"],
            "qualidade": view_ctx["qualidade"],
            "confiabilidade": view_ctx["confiabilidade"],
            "quick_match": view_ctx["quick_match"],
            "importacao_info": view_ctx["importacao_info"],
            "focus_detail": view_ctx["focus_detail"],
            "matrix_context": view_ctx["matrix_context"],
            "coluna_filtrada_aviso": view_ctx["coluna_filtrada_aviso"],
            "macro_pulse": view_ctx["macro_pulse"],
            "matrix_stable_qs": view_ctx["matrix_stable_qs"],
            "is_area_comum": view_ctx["is_area_comum"],
            "embed_mode": embed_mode,
            "layer_nav": view_ctx["layer_nav"],
            "ambiente_id": ambiente_id_ctx,
            "column_groups": view_ctx.get("column_groups") or [],
            "matrix_all_atividades": view_ctx.get("matrix_all_atividades") or [],
            "column_group_selected": view_ctx.get("column_group_selected") or "",
            "column_group_save_url": (
                reverse("engenharia:mapa_controle_salvar_grupos_colunas", args=[ambiente_id_ctx])
                if ambiente_id_ctx
                else ""
            ),
            "matrix_cell_colors": view_ctx.get("matrix_cell_colors") or {},
        },
    )


@login_required
@require_group(GRUPOS.MAPA_CONTROLE)
@require_http_methods(["POST"])
def mapa_controle_salvar_grupos_colunas(request, ambiente_id: int):
    from painel_operacional.models import AmbienteOperacional, AmbienteTipo, AmbienteVersao, VersaoEstado

    payload = _parse_json_body(request)
    raw_groups = payload.get("groups")
    if not isinstance(raw_groups, list):
        return JsonResponse({"success": False, "error": "Payload inválido: groups deve ser lista."}, status=400)

    _, obra = _resolve_obra_for_request(request)
    if not obra:
        return JsonResponse({"success": False, "error": "Obra inválida."}, status=400)
    ambiente = get_object_or_404(
        AmbienteOperacional,
        id=ambiente_id,
        ativo=True,
        tipo=AmbienteTipo.MAPA_CONTROLE,
    )
    if ambiente.obra_id != obra.id:
        return JsonResponse({"success": False, "error": "Ambiente não pertence à obra ativa."}, status=403)

    cleaned_groups = []
    seen_ids = set()
    for item in raw_groups:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        gid = str(item.get("id") or "").strip() or f"grp_{uuid4().hex[:10]}"
        if gid in seen_ids:
            gid = f"{gid}_{len(cleaned_groups) + 1}"
        seen_ids.add(gid)
        cols_raw = item.get("columns")
        cols = []
        if isinstance(cols_raw, list):
            seen_cols = set()
            for col in cols_raw:
                lbl = str(col or "").strip()
                if not lbl or lbl in seen_cols:
                    continue
                seen_cols.add(lbl)
                cols.append(lbl)
        cleaned_groups.append({"id": gid, "name": name[:120], "columns": cols})

    with transaction.atomic():
        draft = ambiente.versoes.filter(estado=VersaoEstado.DRAFT).order_by("-numero").first()
        if not draft:
            draft = AmbienteVersao.objects.create(
                ambiente=ambiente,
                numero=AmbienteVersao.proximo_numero(ambiente.id),
                estado=VersaoEstado.DRAFT,
                layout={},
                metadados={},
            )
        layout = draft.layout if isinstance(draft.layout, dict) else {}
        sections = layout.get("sections")
        if not isinstance(sections, list):
            sections = []
        matrix_section = None
        for section in sections:
            if not isinstance(section, dict):
                continue
            if str(section.get("kind") or "").strip() in {"matrix_table", "table"}:
                matrix_section = section
                break
        if matrix_section is None:
            return JsonResponse({"success": False, "error": "Seção de matriz não encontrada no ambiente."}, status=400)
        data = matrix_section.get("data") if isinstance(matrix_section.get("data"), dict) else {}
        import_meta = data.get("importMeta") if isinstance(data.get("importMeta"), dict) else {}
        data["columnGroups"] = cleaned_groups
        import_meta["column_groups"] = cleaned_groups
        data["importMeta"] = import_meta
        matrix_section["data"] = data
        layout["sections"] = sections
        draft.layout = _normalize_ambiente_layout(layout)
        draft.save(update_fields=["layout", "updated_at"])

    return JsonResponse({"success": True, "groups": cleaned_groups, "obra_id": obra.id, "obra_nome": obra.nome})


@login_required
@require_group(GRUPOS.MAPA_CONTROLE)
@cache_control(no_store=True, no_cache=True, must_revalidate=True, max_age=0)
def importar_mapa_controle(request):
    obras, obra = _resolve_obra_for_request(request)

    if request.method == "POST":
        obra_id = (request.POST.get("obra_id") or "").strip()
        sheet_name = (request.POST.get("sheet") or "DADOS").strip() or "DADOS"
        limpar_antes = bool(request.POST.get("limpar_antes"))
        arquivo = request.FILES.get("arquivo")

        try:
            obra_post = Obra.objects.get(id=int(obra_id), ativa=True)
            if not _user_can_access_obra(request, obra_post):
                messages.error(request, "Você não tem acesso à obra selecionada.")
                return redirect("engenharia:importar_mapa_controle")
        except (ValueError, Obra.DoesNotExist):
            messages.error(request, "Obra inválida para importação.")
            return redirect("engenharia:importar_mapa_controle")

        if not arquivo:
            messages.error(request, "Selecione um arquivo .xlsx para importar.")
            return redirect("engenharia:importar_mapa_controle")

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                for chunk in arquivo.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            call_command(
                "importar_mapa_servico",
                file=tmp_path,
                obra_id=obra_post.id,
                sheet=sheet_name,
                limpar_antes=limpar_antes,
            )
            request.session["obra_id"] = obra_post.id
            request.session.modified = True
            messages.success(request, "Importação do Mapa de Controle concluída com sucesso.")
            return redirect("engenharia:mapa_controle")
        except Exception as exc:
            messages.error(request, f"Erro ao importar: {exc}")
            return redirect("engenharia:importar_mapa_controle")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    importacoes = []
    if obra:
        importacoes = list(
            ImportacaoMapaServico.objects.filter(obra=obra)
            .only("id", "nome_arquivo", "aba_origem", "total_linhas_lidas", "total_linhas_importadas", "created_at")
            .order_by("-created_at")[:20]
        )

    return render(
        request,
        "suprimentos/importar_mapa_controle.html",
        {
            "obras": obras,
            "obra_selecionada": obra,
            "importacoes": importacoes,
        },
    )


@login_required
@require_group(GRUPOS.MAPA_CONTROLE)
@cache_control(no_store=True, no_cache=True, must_revalidate=True, max_age=0)
def mapa_controle_summary(request):
    obra_id = request.GET.get("obra")
    obra = get_object_or_404(Obra, id=obra_id, ativa=True)
    if not _user_can_access_obra(request, obra):
        return JsonResponse({"success": False, "error": "Sem permissão para esta obra."}, status=403)

    filters = _build_filters_from_request(request)
    payload = MapaControleService(obra=obra, filters=filters).build_summary_payload()
    return JsonResponse({"success": True, "data": payload})


@login_required
@require_group(GRUPOS.MAPA_CONTROLE)
@cache_control(no_store=True, no_cache=True, must_revalidate=True, max_age=0)
def mapa_controle_items(request):
    obra_id = request.GET.get("obra")
    obra = get_object_or_404(Obra, id=obra_id, ativa=True)
    if not _user_can_access_obra(request, obra):
        return JsonResponse({"success": False, "error": "Sem permissão para esta obra."}, status=403)

    filters = _build_filters_from_request(request)
    payload = MapaControleService(obra=obra, filters=filters).build_items_payload()
    return JsonResponse({"success": True, "data": payload})
