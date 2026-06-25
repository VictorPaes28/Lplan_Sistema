"""
Página **Análise da Obra** — visão executiva unificada (controle + diário + suprimentos).
API JSON com o mesmo contrato de acesso por obra do Mapa (vínculo a projeto / ProjectMember).
"""

from datetime import date, datetime, timedelta
import hashlib
import json

from accounts.decorators import login_required, require_group
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from accounts.groups import GRUPOS
from core.models import Project
from mapa_obras.models import Obra
from mapa_obras.contexto_obra import resolve_obra_context
from mapa_obras.views import _user_can_access_obra
from django.utils import timezone
from suprimentos.services.analise_obra_service import (
    AnaliseObraFilters,
    AnaliseObraPeriodo,
    AnaliseObraService,
)


# Shell/seções são dados por obra+filtros (não por usuário); TTL maior reduz cold starts.
ANALISE_OBRA_SHELL_CACHE_TTL_SECONDS = 300
ANALISE_OBRA_SECTION_CACHE_TTL_SECONDS = 180
# Sem data_inicio na URL, limita varredura do diário (obra com anos de histórico).
BI_DEFAULT_MAX_PERIOD_DAYS = 90


def _resolve_obra(request):
    return resolve_obra_context(request)


def _parse_periodo(request):
    def _parse(s):
        if not (s or "").strip():
            return None
        try:
            return datetime.strptime(s.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None

    ini = _parse(request.GET.get("data_inicio") or "")
    fim = _parse(request.GET.get("data_fim") or "")
    return ini, fim


def _default_data_inicio_obra(obra: Obra | None):
    """Data inicial padrão do filtro: campo na obra do mapa, senão Project.start_date, senão 30 dias."""
    if obra is None:
        return date.today() - timedelta(days=30)
    inicio_mapa = getattr(obra, "data_inicio", None)
    if inicio_mapa is not None:
        return inicio_mapa
    if obra.project_id:
        sd = Project.objects.filter(pk=obra.project_id).values_list("start_date", flat=True).first()
        if sd:
            return sd
    return date.today() - timedelta(days=30)


def _effective_periodo_analise(request, obra: Obra | None):
    """Período efetivo: querystring ou padrão (início da obra + fim = hoje)."""
    hoje = date.today()
    ini, fim = _parse_periodo(request)
    tem_ini_qs = bool((request.GET.get("data_inicio") or "").strip())
    tem_fim_qs = bool((request.GET.get("data_fim") or "").strip())
    if not tem_ini_qs:
        ini = _default_data_inicio_obra(obra)
    elif ini is None:
        ini = _default_data_inicio_obra(obra) if obra else hoje - timedelta(days=30)
    if not tem_fim_qs:
        fim = hoje
    elif fim is None:
        fim = hoje
    if ini is None:
        ini = hoje - timedelta(days=30)
    if fim is None:
        fim = hoje
    if fim < ini:
        fim = hoje
        if ini > fim:
            ini = fim - timedelta(days=30)
    if not tem_ini_qs and (fim - ini).days > BI_DEFAULT_MAX_PERIOD_DAYS:
        ini = fim - timedelta(days=BI_DEFAULT_MAX_PERIOD_DAYS)
    return ini, fim


def _parse_filtros(request, frente_ctx=None) -> AnaliseObraFilters:
    front_id = (request.GET.get("front") or "").strip()
    if not front_id and frente_ctx is not None:
        front_id = getattr(frente_ctx, 'front_query_value', '') or ''
    return AnaliseObraFilters(
        setor=(request.GET.get("setor") or "").strip(),
        bloco=(request.GET.get("bloco") or "").strip(),
        pavimento=(request.GET.get("pavimento") or "").strip(),
        apto=(request.GET.get("apto") or "").strip(),
        atividade=(request.GET.get("atividade") or "").strip(),
        status_servico=(request.GET.get("status_servico") or "").strip(),
        local_suprimento_id=(request.GET.get("local_suprimento_id") or "").strip(),
        categoria_suprimento=(request.GET.get("categoria_suprimento") or "").strip(),
        prioridade_suprimento=(request.GET.get("prioridade_suprimento") or "").strip(),
        status_suprimento=(request.GET.get("status_suprimento") or "").strip(),
        busca_suprimento=(request.GET.get("busca_suprimento") or "").strip(),
        tag_ocorrencia_id=(request.GET.get("tag_ocorrencia_id") or "").strip(),
        busca_diario_texto=(request.GET.get("busca_diario_texto") or "").strip(),
        responsavel_texto=(request.GET.get("responsavel_texto") or "").strip(),
        front_id=front_id,
    )


def _service_for_request(request, obra: Obra, frente_ctx=None):
    ini, fim = _effective_periodo_analise(request, obra)
    periodo = AnaliseObraPeriodo(data_inicio=ini, data_fim=fim)
    filtros = _parse_filtros(request, frente_ctx)
    return AnaliseObraService(obra, periodo=periodo, filtros=filtros), ini, fim, filtros


def _build_cache_key(
    prefix: str,
    *,
    obra_id: int,
    ini,
    fim,
    filtros: AnaliseObraFilters,
    controle_stamp: str = "",
    extra: str = "",
) -> str:
    filtros_json = json.dumps(filtros.to_dict(), sort_keys=True, ensure_ascii=True)
    raw = (
        f"{prefix}|o:{obra_id}|ini:{ini}|fim:{fim}"
        f"|f:{filtros_json}|mapa:{controle_stamp}|x:{extra}"
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"analise_obra:{prefix}:{digest}"


def _get_cached_payload_or_build(
    request,
    obra: Obra,
    ini,
    fim,
    filtros: AnaliseObraFilters,
    *,
    shell: bool = False,
):
    prefix = "shell" if shell else "full"
    ttl = ANALISE_OBRA_SHELL_CACHE_TTL_SECONDS if shell else ANALISE_OBRA_SECTION_CACHE_TTL_SECONDS
    ini_s = ini.isoformat() if ini else ""
    fim_s = fim.isoformat() if fim else ""
    base_key = _build_cache_key(
        prefix,
        obra_id=obra.id,
        ini=ini_s,
        fim=fim_s,
        filtros=filtros,
        controle_stamp="",
    )
    cached = cache.get(base_key)
    if cached is not None:
        return cached

    periodo = AnaliseObraPeriodo(data_inicio=ini, data_fim=fim)
    svc = AnaliseObraService(obra, periodo=periodo, filtros=filtros)
    controle_stamp = svc.controle_ambiente_cache_stamp()
    stamped_key = _build_cache_key(
        prefix,
        obra_id=obra.id,
        ini=ini_s,
        fim=fim_s,
        filtros=filtros,
        controle_stamp=controle_stamp,
    )
    cached = cache.get(stamped_key)
    if cached is not None:
        return cached

    payload = svc.build_shell_payload() if shell else svc.build_full_payload()
    cache.set(stamped_key, payload, ttl)
    cache.set(base_key, payload, ttl)
    return payload


def _get_cached_section_or_build(
    request,
    obra: Obra,
    ini,
    fim,
    filtros: AnaliseObraFilters,
    svc: AnaliseObraService,
    secao: str,
):
    ini_s = ini.isoformat() if ini else ""
    fim_s = fim.isoformat() if fim else ""
    base_key = _build_cache_key(
        "section",
        obra_id=obra.id,
        ini=ini_s,
        fim=fim_s,
        filtros=filtros,
        controle_stamp="",
        extra=secao,
    )
    cached = cache.get(base_key)
    if cached is not None:
        return cached

    controle_stamp = svc.controle_ambiente_cache_stamp()
    stamped_key = _build_cache_key(
        "section",
        obra_id=obra.id,
        ini=ini_s,
        fim=fim_s,
        filtros=filtros,
        controle_stamp=controle_stamp,
        extra=secao,
    )
    cached = cache.get(stamped_key)
    if cached is not None:
        return cached

    data = svc.build_section(secao)
    if data is not None:
        cache.set(stamped_key, data, ANALISE_OBRA_SECTION_CACHE_TTL_SECONDS)
        cache.set(base_key, data, ANALISE_OBRA_SECTION_CACHE_TTL_SECONDS)
    return data


@login_required
@require_group(GRUPOS.BI_DA_OBRA)
@ensure_csrf_cookie
@cache_control(no_store=True, no_cache=True, must_revalidate=True, max_age=0)
def analise_obra(request):
    ctx = _resolve_obra(request)
    obras, obra = ctx
    payload = None
    filtros = _parse_filtros(request, ctx.frente)
    ini, fim = _effective_periodo_analise(request, obra)

    if obra:
        payload = _get_cached_payload_or_build(request, obra, ini, fim, filtros, shell=True)

    filtros_dict = filtros.to_dict()
    hoje = timezone.localdate()
    advanced_keys = (
        "setor", "bloco", "pavimento", "apto", "atividade", "status_servico",
        "local_suprimento_id", "categoria_suprimento", "prioridade_suprimento",
        "status_suprimento", "busca_suprimento", "tag_ocorrencia_id",
        "busca_diario_texto", "responsavel_texto",
    )
    filtros_avancados_ativos = any((filtros_dict.get(k) or "").strip() for k in advanced_keys)
    return render(
        request,
        "suprimentos/analise_obra.html",
        {
            "analise_payload": payload,
            "restricoes_data_ontem": (hoje - timedelta(days=1)).isoformat(),
            "filtros_get": {
                "data_inicio": ini.isoformat() if ini else "",
                "data_fim": fim.isoformat() if fim else "",
                **filtros_dict,
            },
            "filtros_avancados_ativos": filtros_avancados_ativos,
            **ctx.to_template_context(),
        },
    )


@login_required
@require_group(GRUPOS.BI_DA_OBRA)
@cache_control(no_store=True, no_cache=True, must_revalidate=True, max_age=0)
def analise_obra_resumo(request):
    """Resumo executivo para impressão / Salvar como PDF (window.print)."""
    ctx = _resolve_obra(request)
    obras, obra = ctx
    payload = None
    filtros = _parse_filtros(request, ctx.frente)
    ini, fim = _effective_periodo_analise(request, obra)
    if obra:
        payload = _get_cached_payload_or_build(request, obra, ini, fim, filtros, shell=True)
    return render(
        request,
        "suprimentos/analise_obra_resumo.html",
        {
            "analise_payload": payload,
            "obra_selecionada": obra,
            "filtros_get": {
                "data_inicio": ini.isoformat() if ini else "",
                "data_fim": fim.isoformat() if fim else "",
                **filtros.to_dict(),
            },
            **ctx.to_template_context(),
        },
    )


def _json_error(message: str, status: int = 400):
    return JsonResponse({"success": False, "error": message}, status=status)


@login_required
@require_group(GRUPOS.BI_DA_OBRA)
@cache_control(no_store=True, no_cache=True, must_revalidate=True, max_age=0)
def analise_obra_api(request):
    """
    GET /api/internal/analise-obra/?obra=ID&secao=all|meta|filtros|controle|...
    Mesmas regras de acesso da página HTML (obra no escopo do usuário).
    """
    obra_id = request.GET.get("obra")
    if not obra_id:
        return _json_error("Parâmetro obra é obrigatório.", 400)
    try:
        obra = Obra.objects.get(id=int(obra_id), ativa=True)
    except (ValueError, Obra.DoesNotExist):
        return _json_error("Obra inválida.", 404)

    if not _user_can_access_obra(request, obra):
        return _json_error("Sem permissão para esta obra.", 403)

    ctx = resolve_obra_context(request)
    svc, ini, fim, filtros = _service_for_request(request, obra, ctx.frente)
    secao = (request.GET.get("secao") or "all").strip().lower()
    validas = frozenset(
        {
            "all",
            "full",
            "meta",
            "filtros",
            "controle",
            "suprimentos",
            "diario",
            "cruzamento",
            "heatmap",
            "gestcontroll",
            "restricoes",
            "trackhub",
            "rh",
            "mapa_geo",
            "workflow_central",
        }
    )
    if secao not in validas:
        return _json_error("Parâmetro secao inválido.", 400)
    if secao in {"all", "full"}:
        data = _get_cached_payload_or_build(request, obra, ini, fim, filtros, shell=False)
    else:
        data = _get_cached_section_or_build(request, obra, ini, fim, filtros, svc, secao)
    if data is None:
        return _json_error("Não foi possível montar a seção.", 400)
    return JsonResponse(
        {"success": True, "secao": secao, "data": data},
        json_dumps_params={"default": str},
    )
