from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseForbidden
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie

from accounts.decorators import require_group
from accounts.groups import GRUPOS
from mapa_obras.models import Obra
from mapa_obras.views import _get_obras_for_user, _user_can_access_obra
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


def _build_filters_from_request(request):
    try:
        limit = int(request.GET.get("limit", 200) or 200)
    except ValueError:
        limit = 200
    return MapaControleFilters(
        categoria=(request.GET.get("categoria") or "").strip(),
        local_id=(request.GET.get("local") or "").strip(),
        prioridade=(request.GET.get("prioridade") or "").strip(),
        status=(request.GET.get("status") or "").strip(),
        search=(request.GET.get("search") or "").strip(),
        limit=limit,
    )


@login_required
@require_group(GRUPOS.ENGENHARIA)
@ensure_csrf_cookie
@cache_control(no_store=True, no_cache=True, must_revalidate=True, max_age=0)
def mapa_controle(request):
    if not _is_admin_mapa_controle(request.user):
        return HttpResponseForbidden("Mapa de Controle temporariamente disponível apenas para admin.")

    obras, obra = _resolve_obra_for_request(request)
    summary_payload = None
    filters = _build_filters_from_request(request)
    if obra:
        summary_payload = MapaControleService(obra=obra, filters=filters).build_summary_payload()

    return render(
        request,
        "suprimentos/mapa_controle.html",
        {
            "obras": obras,
            "obra_selecionada": obra,
            "summary_payload": summary_payload,
            "filtros": {
                "categoria": filters.categoria,
                "local": filters.local_id,
                "prioridade": filters.prioridade,
                "status": filters.status,
                "search": filters.search,
            },
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
