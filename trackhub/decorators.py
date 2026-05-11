"""
Controle de acesso TrackHub: superusuário ou um dos papéis do módulo.
Usa PermissionDenied (403) para usuário autenticado sem perfil TrackHub.
"""
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from accounts.groups import GRUPOS


def user_has_trackhub_access(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    allowed = {
        GRUPOS.ADMINISTRADOR,
        GRUPOS.CENTRAL_APROVACOES_ADMIN,
        GRUPOS.TRACKHUB,  # legado
        GRUPOS.TRACKHUB_ADMIN,
        GRUPOS.TRACKHUB_APROVADOR,
        GRUPOS.TRACKHUB_SOLICITANTE,
    }
    return user.groups.filter(name__in=allowed).exists()


def require_trackhub(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(
                request, "Você precisa estar autenticado para acessar esta página."
            )
            return redirect(settings.LOGIN_URL)
        if user_has_trackhub_access(request.user):
            return view_func(request, *args, **kwargs)
        raise PermissionDenied

    return _wrapped_view
