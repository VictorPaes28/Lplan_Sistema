import os
import tempfile
import unicodedata

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponseForbidden
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db.models import Count, Avg, Q, Sum

from accounts.decorators import require_group
from accounts.groups import GRUPOS
from mapa_obras.models import Obra
from mapa_obras.views import _get_obras_for_user, _user_can_access_obra
from suprimentos.models import ImportacaoMapaServico, ItemMapaServico, ItemMapaServicoStatusRef
from suprimentos.services.mapa_controle_service import MapaControleFilters, MapaControleService


def _is_admin_mapa_controle(user):
    """Acesso temporário: somente administrador do sistema."""
    return bool(user and user.is_authenticated and user.is_superuser)


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


def _build_confiabilidade_controle(total_itens: int, qualidade: dict) -> dict:
    if total_itens <= 0:
        return {"score": 0.0, "nivel": "sem_dados"}

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
    elif score >= 85:
        nivel = "bom"
    elif score >= 70:
        nivel = "atenção"
    else:
        nivel = "crítico"
    return {"score": score, "nivel": nivel}


@login_required
@require_group(GRUPOS.ENGENHARIA)
@ensure_csrf_cookie
@cache_control(no_store=True, no_cache=True, must_revalidate=True, max_age=0)
def mapa_controle(request):
    if not _is_admin_mapa_controle(request.user):
        return HttpResponseForbidden("Mapa de Controle temporariamente disponível apenas para admin.")

    obras, obra = _resolve_obra_for_request(request)
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

    status_filter = selected["status"]
    layers = {"setores": [], "blocos": [], "pavimentos": [], "aptos": []}
    itens_atividade = []
    matrix = {"atividades": [], "rows": [], "totais": []}
    kpis = {"total_itens": 0, "percentual_medio": 0.0, "concluidos": 0, "em_andamento": 0, "nao_iniciados": 0}
    qualidade = {
        "sem_bloco": 0,
        "sem_pavimento": 0,
        "sem_apto": 0,
        "sem_status_percentual": 0,
        "sem_data_termino": 0,
    }
    confiabilidade = {"score": 0.0, "nivel": "sem_dados"}
    quick_match = None
    importacao_info = None
    focus_detail = None

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

        layers["setores"] = _layer_aggregates(base_qs, "setor")

        # MATRIZ GERENCIAL (sem inventar: bloco x atividade com %)
        matrix_scope = active_scope_qs

        matrix_items = list(
            matrix_scope.only("bloco", "atividade", "status_percentual", "status_texto").order_by("bloco", "atividade")
        )
        agg = {}
        blocos_set = set()
        atividades_set = set()
        for item in matrix_items:
            bloco = (item.bloco or "SEM BLOCO").strip() or "SEM BLOCO"
            atividade = (item.atividade or "SEM ATIVIDADE").strip() or "SEM ATIVIDADE"
            ratio = _status_to_ratio(item)
            if ratio is None:
                continue
            blocos_set.add(bloco)
            atividades_set.add(atividade)
            key = (bloco, atividade)
            if key not in agg:
                agg[key] = {"sum": 0.0, "count": 0}
            agg[key]["sum"] += ratio
            agg[key]["count"] += 1

        # Mantém painel legível em tela sem perder referência do modelo original.
        atividades = sorted(atividades_set)[:36]
        blocos = sorted(blocos_set)[:60]
        rows = []
        totais = []

        for bloco in blocos:
            cells = []
            row_sum = 0.0
            row_count = 0
            for atividade in atividades:
                data = agg.get((bloco, atividade))
                if data and data["count"] > 0:
                    pct = round((data["sum"] / data["count"]) * 100)
                    row_sum += pct
                    row_count += 1
                    cells.append({"atividade": atividade, "pct": pct})
                else:
                    cells.append({"atividade": atividade, "pct": None})
            total_pct = round(row_sum / row_count) if row_count else None
            rows.append({"bloco": bloco, "cells": cells, "total": total_pct})

        for atividade in atividades:
            col_values = []
            for bloco in blocos:
                data = agg.get((bloco, atividade))
                if data and data["count"] > 0:
                    col_values.append(round((data["sum"] / data["count"]) * 100))
            totais.append(
                {
                    "atividade": atividade,
                    "pct": round(sum(col_values) / len(col_values)) if col_values else None,
                }
            )

        matrix = {"atividades": atividades, "rows": rows, "totais": totais}

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

            apto_agg: dict[tuple[str, str], dict] = {}
            ratio_values: list[float] = []
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
            focus_detail = {
                "bloco": selected["bloco"],
                "atividade": selected["atividade"],
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
            }

        scoped_qs = base_qs
        if selected["setor"]:
            scoped_qs = scoped_qs.filter(setor=selected["setor"])
            layers["blocos"] = _layer_aggregates(scoped_qs, "bloco")
        if selected["bloco"]:
            scoped_qs = scoped_qs.filter(bloco=selected["bloco"])
            layers["pavimentos"] = _layer_aggregates(scoped_qs, "pavimento")
        if selected["pavimento"]:
            scoped_qs = scoped_qs.filter(pavimento=selected["pavimento"])
            layers["aptos"] = _layer_aggregates(scoped_qs, "apto")
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
        },
    )


@login_required
@require_group(GRUPOS.ENGENHARIA)
@cache_control(no_store=True, no_cache=True, must_revalidate=True, max_age=0)
def importar_mapa_controle(request):
    if not _is_admin_mapa_controle(request.user):
        return HttpResponseForbidden("Importação temporariamente disponível apenas para admin.")

    obras, obra = _resolve_obra_for_request(request)

    if request.method == "POST":
        obra_id = (request.POST.get("obra_id") or "").strip()
        sheet_name = (request.POST.get("sheet") or "DADOS").strip() or "DADOS"
        limpar_antes = bool(request.POST.get("limpar_antes"))
        strict_quality = bool(request.POST.get("strict_quality"))
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
                strict_quality=strict_quality,
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
    if not _is_admin_mapa_controle(request.user):
        return JsonResponse(
            {"success": False, "error": "Mapa de Controle temporariamente disponível apenas para admin."},
            status=403,
        )

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
    if not _is_admin_mapa_controle(request.user):
        return JsonResponse(
            {"success": False, "error": "Mapa de Controle temporariamente disponível apenas para admin."},
            status=403,
        )

    obra_id = request.GET.get("obra")
    obra = get_object_or_404(Obra, id=obra_id, ativa=True)
    if not _user_can_access_obra(request, obra):
        return JsonResponse({"success": False, "error": "Sem permissão para esta obra."}, status=403)

    filters = _build_filters_from_request(request)
    payload = MapaControleService(obra=obra, filters=filters).build_items_payload()
    return JsonResponse({"success": True, "data": payload})
