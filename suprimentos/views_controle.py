import os
import tempfile
import unicodedata
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db.models import Count, Avg, Q, Sum

from accounts.decorators import require_group
from accounts.groups import GRUPOS
from mapa_obras.models import Obra
from mapa_obras.views import _get_obras_for_user, _user_can_access_obra
from suprimentos.models import ImportacaoMapaServico, ItemMapaServico, ItemMapaServicoStatusRef
from suprimentos.services.mapa_controle_service import MapaControleFilters, MapaControleService


def _resolve_obra_for_request(request):
    obras = _get_obras_for_user(request)
    obra_param = request.GET.get("obra")
    obra = None

    if obra_param:
        try:
            obra = Obra.objects.get(id=int(obra_param), ativa=True)
            if not _user_can_access_obra(request, obra):
                obra = None
        except (Obra.DoesNotExist, ValueError):
            obra = None

    if not obra:
        obra_sessao_id = request.session.get("obra_id")
        if obra_sessao_id:
            try:
                obra = Obra.objects.get(id=int(obra_sessao_id), ativa=True)
                if not _user_can_access_obra(request, obra):
                    obra = None
            except (Obra.DoesNotExist, ValueError):
                obra = None

    if not obra:
        obra = obras.first()

    if obra:
        request.session["obra_id"] = obra.id
        request.session.modified = True
    return obras, obra


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


def _build_layers_navigation(raw_qs, selected: dict) -> dict:
    """
    Opções dos chips de camada: lista completa de irmãos no recorte geográfico.
    Não aplica filtro de coluna (atividade), busca nem status — assim ao escolher
    um bloco não somem os outros (A/B/C) nem os setores irmãos.
    """
    layers: dict[str, list] = {"setores": [], "blocos": [], "pavimentos": [], "aptos": []}
    layers["setores"] = _layer_aggregates(raw_qs, "setor")
    if not (selected.get("setor") or "").strip():
        return layers
    qs_bl = raw_qs.filter(setor=selected["setor"])
    layers["blocos"] = _layer_aggregates(qs_bl, "bloco")
    if not (selected.get("bloco") or "").strip():
        return layers
    qs_pav = qs_bl.filter(bloco=selected["bloco"])
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
    """Modos alternativos exigem camadas mínimas para fazer sentido na obra."""
    r = (requested or "").strip().lower()
    if r not in ("bloco", "pavimento", "apto"):
        r = "bloco"
    if _setor_e_area_comum((selected.get("setor") or "")):
        # Sem modo por unidade; pedidos de "apto" caem em pavimento.
        if r == "apto":
            r = "pavimento"
        if r == "pavimento" and selected.get("bloco"):
            return "pavimento"
        return "bloco"
    if r == "apto" and selected.get("bloco") and selected.get("pavimento"):
        return "apto"
    if r == "pavimento" and selected.get("bloco"):
        return "pavimento"
    return "bloco"


def _row_field_for_matrix_mode(mode: str) -> str:
    return {"bloco": "bloco", "pavimento": "pavimento", "apto": "apto"}.get(mode, "bloco")


def _default_label_for_row_field(row_field: str) -> str:
    return {
        "bloco": "SEM BLOCO",
        "pavimento": "SEM PAVIMENTO",
        "apto": "SEM APTO",
    }.get(row_field, "SEM REGISTRO")


def _build_matrix_grid(
    matrix_scope_qs,
    row_field: str,
    atividades_max: int = 36,
    rows_max: int = 60,
) -> dict:
    """Agrega percentuais em uma grade (linha x atividade), ex.: bloco×atividade ou pavimento×atividade."""
    default_row = _default_label_for_row_field(row_field)
    only_fields = [row_field, "atividade", "status_percentual", "status_texto"]
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
        if key not in agg:
            agg[key] = {"sum": 0.0, "count": 0}
        agg[key]["sum"] += ratio
        agg[key]["count"] += 1

    atividades = sorted(atividades_set)[:atividades_max]
    rows_sorted = sorted(rows_set)[:rows_max]
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
@require_group(GRUPOS.ENGENHARIA)
@ensure_csrf_cookie
@cache_control(no_store=True, no_cache=True, must_revalidate=True, max_age=0)
def mapa_controle(request):
    obras, obra = _resolve_obra_for_request(request)
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
    }
    is_area_comum = False

    status_filter = selected["status"]
    layers = {"setores": [], "blocos": [], "pavimentos": [], "aptos": []}
    itens_atividade = []
    matrix = {
        "atividades": [],
        "rows": [],
        "totais": [],
        "mode": "bloco",
        "header_first_col": "Bloco",
    }
    kpis = {"total_itens": 0, "percentual_medio": 0.0, "concluidos": 0, "em_andamento": 0, "nao_iniciados": 0}
    qualidade = {
        "sem_bloco": 0,
        "sem_pavimento": 0,
        "sem_apto": 0,
        "sem_status_percentual": 0,
        "sem_data_termino": 0,
    }
    confiabilidade = {"score": 0.0, "nivel": "sem_dados", "nivel_display": "Sem dados"}
    quick_match = None
    importacao_info = None
    focus_detail = None
    matrix_context = None

    if obra:
        raw_qs = ItemMapaServico.objects.filter(obra=obra)
        base_qs = raw_qs
        latest_import = ImportacaoMapaServico.objects.filter(obra=obra).only(
            "created_at", "nome_arquivo", "total_linhas_lidas", "total_linhas_importadas", "aba_origem"
        ).first()
        if latest_import:
            importacao_info = {
                "created_at": latest_import.created_at,
                "nome_arquivo": latest_import.nome_arquivo,
                "total_linhas_lidas": latest_import.total_linhas_lidas,
                "total_linhas_importadas": latest_import.total_linhas_importadas,
                "aba_origem": latest_import.aba_origem,
            }

        # Busca rápida: tenta levar o usuário para a camada mais específica
        # sem precisar abrir setor > bloco > pavimento > apto manualmente.
        quick_find = selected["quick_find"]
        if quick_find and not selected["apto"]:
            quick_qs = base_qs.filter(
                Q(setor__icontains=quick_find)
                | Q(bloco__icontains=quick_find)
                | Q(pavimento__icontains=quick_find)
                | Q(apto__icontains=quick_find)
                | Q(atividade__icontains=quick_find)
                | Q(grupo_servicos__icontains=quick_find)
            )
            candidate = quick_qs.order_by("setor", "bloco", "pavimento", "apto", "atividade").first()
            if candidate:
                selected["setor"] = candidate.setor or selected["setor"]
                selected["bloco"] = candidate.bloco or selected["bloco"]
                selected["pavimento"] = candidate.pavimento or selected["pavimento"]
                selected["apto"] = candidate.apto or selected["apto"]
                quick_match = {
                    "query": quick_find,
                    "setor": candidate.setor,
                    "bloco": candidate.bloco,
                    "pavimento": candidate.pavimento,
                    "apto": candidate.apto,
                    "atividade": candidate.atividade,
                }

        is_area_comum = _setor_e_area_comum(selected.get("setor") or "")
        if is_area_comum:
            selected["apto"] = ""

        if selected["search"]:
            s = selected["search"]
            base_qs = base_qs.filter(
                Q(atividade__icontains=s)
                | Q(grupo_servicos__icontains=s)
                | Q(setor__icontains=s)
                | Q(bloco__icontains=s)
                | Q(pavimento__icontains=s)
                | Q(apto__icontains=s)
                | Q(status_texto__icontains=s)
                | Q(observacao__icontains=s)
            )
        if selected["atividade"]:
            base_qs = base_qs.filter(atividade__icontains=selected["atividade"])

        if status_filter == "concluido":
            base_qs = base_qs.filter(Q(status_percentual__gte=1) | Q(status_texto__icontains="conclu"))
        elif status_filter == "em_andamento":
            base_qs = base_qs.filter(
                Q(status_percentual__gt=0, status_percentual__lt=1)
                | Q(status_texto__icontains="exec")
                | Q(status_texto__icontains="parcial")
            )
        elif status_filter == "nao_iniciado":
            base_qs = base_qs.filter(
                Q(status_percentual__lte=0)
                | Q(status_texto__icontains="nao")
                | Q(status_texto__icontains="não")
                | Q(status_texto__icontains="pend")
            )

        # Escopo hierárquico ativo (camadas selecionadas) aplicado em todos os painéis.
        active_scope_qs = base_qs
        if selected["setor"]:
            active_scope_qs = active_scope_qs.filter(setor=selected["setor"])
        if selected["bloco"]:
            active_scope_qs = active_scope_qs.filter(bloco=selected["bloco"])
        if selected["pavimento"]:
            active_scope_qs = active_scope_qs.filter(pavimento=selected["pavimento"])
        if selected["apto"]:
            active_scope_qs = active_scope_qs.filter(apto=selected["apto"])

        layers = _build_layers_navigation(raw_qs, selected)

        # MATRIZ GERENCIAL — bloco / pavimento / apto × atividade (dimensão de linha variável)
        matrix_scope = active_scope_qs
        matrix_mode = _resolve_matrix_mode(request.GET.get("matrix_mode") or "", selected)
        row_field = _row_field_for_matrix_mode(matrix_mode)
        rows_max = 80 if matrix_mode == "apto" else 60
        matrix = _build_matrix_grid(matrix_scope, row_field, rows_max=rows_max)
        matrix["mode"] = matrix_mode
        matrix["row_field"] = row_field
        matrix["header_first_col"] = {
            "bloco": "Bloco",
            "pavimento": "Pavimento",
            "apto": "Apto / und.",
        }.get(matrix_mode, "Bloco")

        # Detalhe contextual da célula escolhida (ex.: BL1 x ARMAÇÃO LAJE = 77%)
        if selected["bloco"] and selected["atividade"]:
            focus_qs = raw_qs.filter(bloco=selected["bloco"], atividade__iexact=selected["atividade"])
            if selected["setor"]:
                focus_qs = focus_qs.filter(setor=selected["setor"])
            if selected["pavimento"]:
                focus_qs = focus_qs.filter(pavimento=selected["pavimento"])
            if selected["apto"]:
                focus_qs = focus_qs.filter(apto=selected["apto"])
            if status_filter == "concluido":
                focus_qs = focus_qs.filter(Q(status_percentual__gte=1) | Q(status_texto__icontains="conclu"))
            elif status_filter == "em_andamento":
                focus_qs = focus_qs.filter(
                    Q(status_percentual__gt=0, status_percentual__lt=1)
                    | Q(status_texto__icontains="exec")
                    | Q(status_texto__icontains="parcial")
                )
            elif status_filter == "nao_iniciado":
                focus_qs = focus_qs.filter(
                    Q(status_percentual__lte=0)
                    | Q(status_texto__icontains="nao")
                    | Q(status_texto__icontains="não")
                    | Q(status_texto__icontains="pend")
                )

            if is_area_comum:
                # Agrega por pavimento (apartamento não existe neste setor).
                pav_agg: dict[str, dict] = {}
                ratio_values: list[float] = []
                for item in focus_qs.only(
                    "pavimento", "status_texto", "status_percentual", "data_termino", "observacao"
                ):
                    ratio = _status_to_ratio(item)
                    if ratio is not None:
                        ratio_values.append(ratio)
                    pk = (item.pavimento or "-").strip() or "-"
                    if pk not in pav_agg:
                        pav_agg[pk] = {
                            "pavimento": pk,
                            "sum_ratio": 0.0,
                            "count_ratio": 0,
                            "status_texto": item.status_texto or "",
                            "data_termino": item.data_termino,
                            "observacao": (item.observacao or "")[:120],
                        }
                    if ratio is not None:
                        pav_agg[pk]["sum_ratio"] += ratio
                        pav_agg[pk]["count_ratio"] += 1

                apto_rows = []
                concluidos = 0
                em_andamento = 0
                nao_iniciados = 0
                for _, data in pav_agg.items():
                    avg_ratio = (
                        data["sum_ratio"] / data["count_ratio"] if data["count_ratio"] > 0 else None
                    )
                    bucket = _status_bucket_from_ratio(avg_ratio)
                    if bucket == "concluido":
                        concluidos += 1
                    elif bucket == "em_andamento":
                        em_andamento += 1
                    elif bucket == "nao_iniciado":
                        nao_iniciados += 1
                    apto_rows.append(
                        {
                            "apto": None,
                            "pavimento": data["pavimento"],
                            "pct": round((avg_ratio or 0) * 100) if avg_ratio is not None else None,
                            "status_bucket": bucket,
                            "status_texto": data["status_texto"] or "-",
                            "data_termino": data["data_termino"],
                            "observacao": data["observacao"] or "-",
                        }
                    )
                apto_rows.sort(key=lambda r: (r["pct"] is None, r["pct"] if r["pct"] is not None else 999))
                media_pct = round((sum(ratio_values) / len(ratio_values)) * 100) if ratio_values else None
            else:
                apto_agg: dict[tuple[str, str], dict] = {}
                ratio_values = []
                for item in focus_qs.only(
                    "apto", "pavimento", "status_texto", "status_percentual", "data_termino", "observacao"
                ):
                    ratio = _status_to_ratio(item)
                    if ratio is not None:
                        ratio_values.append(ratio)
                    apto_key = ((item.apto or "SEM APTO").strip() or "SEM APTO", (item.pavimento or "-").strip() or "-")
                    if apto_key not in apto_agg:
                        apto_agg[apto_key] = {
                            "apto": apto_key[0],
                            "pavimento": apto_key[1],
                            "sum_ratio": 0.0,
                            "count_ratio": 0,
                            "status_texto": item.status_texto or "",
                            "data_termino": item.data_termino,
                            "observacao": (item.observacao or "")[:120],
                        }
                    if ratio is not None:
                        apto_agg[apto_key]["sum_ratio"] += ratio
                        apto_agg[apto_key]["count_ratio"] += 1

                apto_rows = []
                concluidos = 0
                em_andamento = 0
                nao_iniciados = 0
                for _, data in apto_agg.items():
                    avg_ratio = (
                        data["sum_ratio"] / data["count_ratio"] if data["count_ratio"] > 0 else None
                    )
                    bucket = _status_bucket_from_ratio(avg_ratio)
                    if bucket == "concluido":
                        concluidos += 1
                    elif bucket == "em_andamento":
                        em_andamento += 1
                    elif bucket == "nao_iniciado":
                        nao_iniciados += 1
                    apto_rows.append(
                        {
                            "apto": data["apto"],
                            "pavimento": data["pavimento"],
                            "pct": round((avg_ratio or 0) * 100) if avg_ratio is not None else None,
                            "status_bucket": bucket,
                            "status_texto": data["status_texto"] or "-",
                            "data_termino": data["data_termino"],
                            "observacao": data["observacao"] or "-",
                        }
                    )

                apto_rows.sort(key=lambda r: (r["pct"] is None, r["pct"] if r["pct"] is not None else 999))
                media_pct = round((sum(ratio_values) / len(ratio_values)) * 100) if ratio_values else None
            status_ref = (
                ItemMapaServicoStatusRef.objects.filter(
                    obra=obra,
                    atividade_chave=_norm_key(selected["atividade"]),
                )
                .only("status_macro", "situacao", "prazo_execucao", "responsabilidade")
                .first()
            )
            _recorte = []
            if selected["setor"]:
                _recorte.append(f"Setor: {selected['setor']}")
            if selected["pavimento"]:
                _recorte.append(f"Pavimento: {selected['pavimento']}")
            if selected["apto"]:
                _recorte.append(f"Unidade: {selected['apto']}")
            focus_detail = {
                "bloco": selected["bloco"],
                "atividade": selected["atividade"],
                "recorte_linha": " · ".join(_recorte),
                "registros_linhas": focus_qs.count(),
                "pct_na_grade": grid_pct_clicado,
                "media_pct": media_pct,
                "total_aptos": len(apto_rows),
                "concluidos": concluidos,
                "em_andamento": em_andamento,
                "nao_iniciados": nao_iniciados,
                "rows": apto_rows[:80],
                "status_macro": status_ref.status_macro if status_ref else "",
                "situacao": status_ref.situacao if status_ref else "",
                "prazo_execucao": status_ref.prazo_execucao if status_ref else "",
                "responsabilidade": status_ref.responsabilidade if status_ref else "",
                "omitir_apto": is_area_comum,
            }

        scoped_qs = base_qs
        if selected["setor"]:
            scoped_qs = scoped_qs.filter(setor=selected["setor"])
        if selected["bloco"]:
            scoped_qs = scoped_qs.filter(bloco=selected["bloco"])
        if selected["pavimento"]:
            scoped_qs = scoped_qs.filter(pavimento=selected["pavimento"])
        if selected["apto"]:
            scoped_qs = scoped_qs.filter(apto=selected["apto"])
            itens_atividade = list(
                scoped_qs.values(
                    "atividade",
                    "grupo_servicos",
                    "status_texto",
                    "status_percentual",
                    "observacao",
                    "custo",
                    "data_termino",
                ).order_by("grupo_servicos", "atividade")
            )[:500]
            for row in itens_atividade:
                pct = row.get("status_percentual")
                if pct is None:
                    row["pct_display"] = None
                    continue
                try:
                    pct_value = float(pct)
                except (TypeError, ValueError):
                    row["pct_display"] = None
                    continue
                if pct_value <= 1:
                    pct_value = pct_value * 100
                row["pct_display"] = round(pct_value, 2)
        elif is_area_comum and selected["pavimento"]:
            itens_atividade = list(
                scoped_qs.values(
                    "atividade",
                    "grupo_servicos",
                    "status_texto",
                    "status_percentual",
                    "observacao",
                    "custo",
                    "data_termino",
                ).order_by("grupo_servicos", "atividade")
            )[:500]
            for row in itens_atividade:
                pct = row.get("status_percentual")
                if pct is None:
                    row["pct_display"] = None
                    continue
                try:
                    pct_value = float(pct)
                except (TypeError, ValueError):
                    row["pct_display"] = None
                    continue
                if pct_value <= 1:
                    pct_value = pct_value * 100
                row["pct_display"] = round(pct_value, 2)

        all_items = list(active_scope_qs.only("status_percentual", "status_texto"))
        total_itens = len(all_items)
        concluidos = 0
        em_andamento = 0
        nao_iniciados = 0
        soma_pct = 0.0
        pct_count = 0
        for item in all_items:
            status_txt = (item.status_texto or "").lower()
            if item.status_percentual is not None:
                pct = float(item.status_percentual)
                soma_pct += pct
                pct_count += 1
                if pct >= 1:
                    concluidos += 1
                elif pct <= 0:
                    nao_iniciados += 1
                else:
                    em_andamento += 1
            elif "conclu" in status_txt:
                concluidos += 1
            elif "exec" in status_txt or "parcial" in status_txt:
                em_andamento += 1
            else:
                nao_iniciados += 1

        kpis = {
            "total_itens": total_itens,
            "percentual_medio": round((soma_pct / pct_count) * 100, 2) if pct_count else 0.0,
            "concluidos": concluidos,
            "em_andamento": em_andamento,
            "nao_iniciados": nao_iniciados,
        }
        qualidade = {
            "sem_bloco": active_scope_qs.filter(Q(bloco__isnull=True) | Q(bloco__exact="")).count(),
            "sem_pavimento": active_scope_qs.filter(Q(pavimento__isnull=True) | Q(pavimento__exact="")).count(),
            "sem_apto": active_scope_qs.filter(Q(apto__isnull=True) | Q(apto__exact="")).count(),
            "sem_status_percentual": active_scope_qs.filter(status_percentual__isnull=True).count(),
            "sem_data_termino": active_scope_qs.filter(data_termino__isnull=True).count(),
        }
        confiabilidade = _build_confiabilidade_controle(kpis["total_itens"], qualidade)

        _st_lbl = {
            "": "Qualquer status",
            "concluido": "Só concluídos",
            "em_andamento": "Só em andamento",
            "nao_iniciado": "Só não iniciados",
        }
        _path_segs = []
        if selected["setor"]:
            _path_segs.append(f"Setor: {selected['setor']}")
        if selected["bloco"]:
            _path_segs.append(f"Bloco: {selected['bloco']}")
        if selected["pavimento"]:
            _path_segs.append(f"Pav.: {selected['pavimento']}")
        if selected["apto"]:
            _path_segs.append(f"Unid.: {selected['apto']}")
        if selected["atividade"]:
            _path_segs.append(f"Ativ. (coluna): {selected['atividade']}")
        _modo_grade = {
            "bloco": "Bloco × atividade",
            "pavimento": "Pavimento × atividade",
            "apto": "Unidade × atividade",
        }.get(matrix.get("mode", "bloco"), "Bloco × atividade")
        matrix_context = {
            "obra_titulo": f"{obra.codigo_sienge} — {obra.nome}",
            "caminho": " › ".join(_path_segs) if _path_segs else "Obra inteira — sem recorte de localização",
            "status_filtro": _st_lbl.get(selected["status"], selected["status"] or "Qualquer status"),
            "modo_grade_label": _modo_grade,
            "n_grade_linhas": len(matrix.get("rows") or []),
            "n_grade_cols": len(matrix.get("atividades") or []),
            "cnt_setores": len(layers["setores"]),
            "cnt_blocos_camada": len(layers["blocos"]) if layers["blocos"] else None,
            "cnt_pavs_camada": len(layers["pavimentos"]) if layers["pavimentos"] else None,
            "cnt_unids_camada": len(layers["aptos"]) if layers["aptos"] else None,
        }

    # Query estável para chips da matriz (filtros de texto/status; sem recorte setor/bloco/…).
    matrix_stable_qs = ""
    if obra:
        matrix_stable_qs = urlencode(
            {
                "status": selected["status"],
                "search": selected["search"],
                "quick": selected["quick_find"],
                "atividade": selected["atividade"],
                "matrix_mode": matrix.get("mode") or "bloco",
            }
        )

    coluna_filtrada_aviso = None
    if obra and selected["atividade"] and not focus_detail:
        coluna_filtrada_aviso = selected["atividade"]

    macro_pulse = _macro_pulse(kpis, confiabilidade, qualidade) if obra else None

    return render(
        request,
        "suprimentos/mapa_controle.html",
        {
            "obras": obras,
            "obra_selecionada": obra,
            "selected": selected,
            "layers": layers,
            "itens_atividade": itens_atividade,
            "matrix": matrix,
            "kpis": kpis,
            "qualidade": qualidade,
            "confiabilidade": confiabilidade,
            "quick_match": quick_match,
            "importacao_info": importacao_info,
            "focus_detail": focus_detail,
            "matrix_context": matrix_context,
            "coluna_filtrada_aviso": coluna_filtrada_aviso,
            "macro_pulse": macro_pulse,
            "matrix_stable_qs": matrix_stable_qs,
            "is_area_comum": is_area_comum,
        },
    )


@login_required
@require_group(GRUPOS.ENGENHARIA)
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
@require_group(GRUPOS.ENGENHARIA)
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
@require_group(GRUPOS.ENGENHARIA)
@cache_control(no_store=True, no_cache=True, must_revalidate=True, max_age=0)
def mapa_controle_items(request):
    obra_id = request.GET.get("obra")
    obra = get_object_or_404(Obra, id=obra_id, ativa=True)
    if not _user_can_access_obra(request, obra):
        return JsonResponse({"success": False, "error": "Sem permissão para esta obra."}, status=403)

    filters = _build_filters_from_request(request)
    payload = MapaControleService(obra=obra, filters=filters).build_items_payload()
    return JsonResponse({"success": True, "data": payload})
