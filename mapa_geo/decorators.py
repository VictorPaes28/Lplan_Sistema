from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from accounts.groups import usuario_tem_acesso_mapa_geografico
from core.frontend_views import get_selected_project, _user_can_access_project
from core.models import Project


def _user_has_mapa_geo_access(user) -> bool:
    return usuario_tem_acesso_mapa_geografico(user)


def mapa_geo_access_required(view_func):
    """Exige grupo Diário de Obra (ou staff) para acessar o Mapa Geográfico."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not _user_has_mapa_geo_access(request.user):
            messages.warning(request, 'Você não tem permissão para acessar o Mapa Geográfico.')
            return redirect('select-system')
        return view_func(request, *args, **kwargs)

    return wrapper


def mapa_project_required(view_func):
    """Garante obra selecionada; redireciona para o seletor do mapa (não do Diário)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        pid_raw = (request.GET.get('project') or request.GET.get('obra') or '').strip()
        if pid_raw.isdigit():
            try:
                proj = Project.objects.get(pk=int(pid_raw))
            except (Project.DoesNotExist, ValueError, TypeError):
                proj = None
            if proj and _user_can_access_project(request.user, proj):
                request.session['selected_project_id'] = proj.id
                request.session['selected_project_name'] = proj.name
                request.session['selected_project_code'] = proj.code
                request.session.modified = True

        if 'selected_project_id' not in request.session:
            return redirect('mapa_geo:selecionar_obra')

        project = get_selected_project(request)
        if not project:
            return redirect('mapa_geo:selecionar_obra')

        if not _user_can_access_project(request.user, project):
            for key in ('selected_project_id', 'selected_project_name', 'selected_project_code'):
                request.session.pop(key, None)
            messages.warning(request, 'Você não está mais vinculado a essa obra. Selecione outra.')
            return redirect('mapa_geo:selecionar_obra')

        return view_func(request, *args, **kwargs)

    return wrapper

