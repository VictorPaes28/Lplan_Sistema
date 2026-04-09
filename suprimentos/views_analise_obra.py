"""
Página **Análise da Obra** — visão executiva unificada (controle + diário + suprimentos).
API JSON com o mesmo contrato de acesso por obra do Mapa (vínculo a projeto / ProjectMember).
"""

from datetime import date, datetime, timedelta

from accounts.decorators import login_required, require_group
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from accounts.groups import GRUPOS
from mapa_obras.models import Obra
from mapa_obras.views import _get_obras_for_user, _user_can_access_obra
from suprimentos.services.analise_obra_service import (
    AnaliseObraFilters,
    AnaliseObraPeriodo,
    AnaliseObraService,
)


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
    ini, fim = _parse_periodo(request)
    hoje = date.today()
    if not ini or not fim or fim < ini:
        fim = hoje
        ini = hoje - timedelta(days=30)
    periodo = AnaliseObraPeriodo(data_inicio=ini, data_fim=fim)
    filtros = _parse_filtros(request)
    return AnaliseObraService(obra, periodo=periodo, filtros=filtros), ini, fim, filtros


@login_required
@require_group(GRUPOS.ENGENHARIA, GRUPOS.GERENTES)
@ensure_csrf_cookie
@cache_control(no_store=True, no_cache=True, must_revalidate=True, max_age=0)
def analise_obra(request):
    obras, obra = _resolve_obra(request)
    payload = None
    ini, fim = _parse_periodo(request)
    filtros = _parse_filtros(request)

    hoje = date.today()
    if obra:
        if not ini or not fim or fim < ini:
            fim = hoje
            ini = hoje - timedelta(days=30)
        periodo = AnaliseObraPeriodo(data_inicio=ini, data_fim=fim)
        svc = AnaliseObraService(obra, periodo=periodo, filtros=filtros)
        payload = svc.build_payload()

    filtros_dict = filtros.to_dict()
    return render(
        request,
        "suprimentos/analise_obra.html",
        {
            "obras": obras,
            "obra_selecionada": obra,
            "analise_payload": payload,
            "filtros_get": {
                "data_inicio": ini.isoformat() if obra and ini else "",
                "data_fim": fim.isoformat() if obra and fim else "",
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

    svc, _, _, _ = _service_for_request(request, obra)
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
    data = svc.build_section(secao)
    if data is None:
        return _json_error("Não foi possível montar a seção.", 400)
    return JsonResponse({"success": True, "secao": secao, "data": data})


@login_required
@require_group(GRUPOS.ENGENHARIA, GRUPOS.GERENTES)
@cache_control(no_store=True, no_cache=True, must_revalidate=True, max_age=0)
def analise_obra_drilldown_api(request):
    """GET .../analise-obra/drilldown/?obra=&bloco=&pavimento= — detalhe para drawer."""
    obra_id = request.GET.get("obra")
    bloco = (request.GET.get("bloco") or "").strip()
    pavimento = (request.GET.get("pavimento") or "").strip()
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
    payload = svc.build_drill_down(bloco, pavimento)
    return JsonResponse({"success": True, "data": payload})
