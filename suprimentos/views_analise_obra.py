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
from mapa_obras.views import _get_obras_for_user, _user_can_access_obra
from suprimentos.services.analise_obra_service import (
    AnaliseObraFilters,
    AnaliseObraPeriodo,
    AnaliseObraService,
)

ANALISE_OBRA_CACHE_TTL_SECONDS = 120


def _resolve_obra(request):
    obras = _get_obras_for_user(request)
    obra_param = request.GET.get("obra")
    obra = None
    if obra_param:
        try:
            obra = Obra.objects.get(id=int(obra_param), ativa=True)
            if not _user_can_access_obra(request, obra):
                obra = None
        except (ValueError, Obra.DoesNotExist):
            obra = None
    if not obra:
        sid = request.session.get("obra_id")
        if sid:
            try:
                obra = Obra.objects.get(id=int(sid), ativa=True)
                if not _user_can_access_obra(request, obra):
                    obra = None
            except (ValueError, Obra.DoesNotExist):
                obra = None
    if not obra:
        obra = obras.first()
    if obra:
        request.session["obra_id"] = obra.id
        request.session.modified = True
    return obras, obra


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
    return ini, fim


def _parse_filtros(request) -> AnaliseObraFilters:
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
        visao=(request.GET.get("visao") or "geral").strip() or "geral",
    )


def _service_for_request(request, obra: Obra):
    ini, fim = _effective_periodo_analise(request, obra)
    periodo = AnaliseObraPeriodo(data_inicio=ini, data_fim=fim)
    filtros = _parse_filtros(request)
    return AnaliseObraService(obra, periodo=periodo, filtros=filtros), ini, fim, filtros


def _build_cache_key(prefix: str, *, user_id: int, obra_id: int, ini, fim, filtros: AnaliseObraFilters, extra: str = "") -> str:
    filtros_json = json.dumps(filtros.to_dict(), sort_keys=True, ensure_ascii=True)
    raw = f"{prefix}|u:{user_id}|o:{obra_id}|ini:{ini}|fim:{fim}|f:{filtros_json}|x:{extra}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"analise_obra:{prefix}:{digest}"


def _get_cached_payload_or_build(request, obra: Obra, ini, fim, filtros: AnaliseObraFilters):
    key = _build_cache_key(
        "full",
        user_id=request.user.id,
        obra_id=obra.id,
        ini=ini.isoformat() if ini else "",
        fim=fim.isoformat() if fim else "",
        filtros=filtros,
    )
    cached = cache.get(key)
    if cached is not None:
        return cached
    periodo = AnaliseObraPeriodo(data_inicio=ini, data_fim=fim)
    svc = AnaliseObraService(obra, periodo=periodo, filtros=filtros)
    payload = svc.build_payload()
    cache.set(key, payload, ANALISE_OBRA_CACHE_TTL_SECONDS)
    return payload


@login_required
@require_group(GRUPOS.ENGENHARIA, GRUPOS.GERENTES)
@ensure_csrf_cookie
@cache_control(no_store=True, no_cache=True, must_revalidate=True, max_age=0)
def analise_obra(request):
    obras, obra = _resolve_obra(request)
    payload = None
    filtros = _parse_filtros(request)
    ini, fim = _effective_periodo_analise(request, obra)

    if obra:
        payload = _get_cached_payload_or_build(request, obra, ini, fim, filtros)

    filtros_dict = filtros.to_dict()
    return render(
        request,
        "suprimentos/analise_obra.html",
        {
            "obras": obras,
            "obra_selecionada": obra,
            "analise_payload": payload,
            "filtros_get": {
                "data_inicio": ini.isoformat() if ini else "",
                "data_fim": fim.isoformat() if fim else "",
                **filtros_dict,
            },
        },
    )


def _json_error(message: str, status: int = 400):
    return JsonResponse({"success": False, "error": message}, status=status)


@login_required
@require_group(GRUPOS.ENGENHARIA, GRUPOS.GERENTES)
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

    svc, ini, fim, filtros = _service_for_request(request, obra)
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
        }
    )
    if secao not in validas:
        return _json_error("Parâmetro secao inválido.", 400)
    if secao in {"all", "full"}:
        data = _get_cached_payload_or_build(request, obra, ini, fim, filtros)
    else:
        key = _build_cache_key(
            "section",
            user_id=request.user.id,
            obra_id=obra.id,
            ini=ini.isoformat() if ini else "",
            fim=fim.isoformat() if fim else "",
            filtros=filtros,
            extra=secao,
        )
        data = cache.get(key)
        if data is None:
            data = svc.build_section(secao)
            if data is not None:
                cache.set(key, data, ANALISE_OBRA_CACHE_TTL_SECONDS)
    if data is None:
        return _json_error("Não foi possível montar a seção.", 400)
    return JsonResponse(
        {"success": True, "secao": secao, "data": data},
        json_dumps_params={"default": str},
    )


@login_required
@require_group(GRUPOS.ENGENHARIA, GRUPOS.GERENTES)
@cache_control(no_store=True, no_cache=True, must_revalidate=True, max_age=0)
def analise_obra_drilldown_api(request):
    """GET .../analise-obra/drilldown/?obra=&bloco=&pavimento= — detalhe para drawer."""
    obra_id = request.GET.get("obra")
    bloco = (request.GET.get("bloco") or "").strip()
    pavimento = (request.GET.get("pavimento") or "").strip()
    setor = (request.GET.get("setor") or "").strip()
    if not obra_id:
        return _json_error("Parâmetro obra é obrigatório.", 400)
    if not bloco:
        return _json_error("Parâmetro bloco é obrigatório.", 400)
    try:
        obra = Obra.objects.get(id=int(obra_id), ativa=True)
    except (ValueError, Obra.DoesNotExist):
        return _json_error("Obra inválida.", 404)

    if not _user_can_access_obra(request, obra):
        return _json_error("Sem permissão para esta obra.", 403)

    svc, _, _, _ = _service_for_request(request, obra)
    payload = svc.build_drill_down(bloco, pavimento, setor=setor or None)
    return JsonResponse(
        {"success": True, "data": payload},
        json_dumps_params={"default": str},
    )
