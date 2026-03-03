from functools import wraps
from django.shortcuts import redirect
from django.conf import settings
from django.contrib import messages


def require_group(*group_names):
    """
    Decorator para verificar se o usuário pertence a um dos grupos especificados.
    Superusers sempre têm acesso.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'Você precisa estar autenticado para acessar esta página.')
                return redirect(settings.LOGIN_URL)
            
            # Superusers sempre têm acesso a tudo
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            if not request.user.groups.filter(name__in=group_names).exists():
                messages.error(request, 'Você não tem permissão para acessar esta página.')
                return redirect('select-system')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

