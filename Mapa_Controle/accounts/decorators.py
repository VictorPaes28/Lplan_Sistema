from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def require_group(*group_names):
    """
    Decorator para verificar se o usuário pertence a um dos grupos especificados.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'Você precisa estar autenticado para acessar esta página.')
                return redirect('login')
            
            if not request.user.groups.filter(name__in=group_names).exists():
                messages.error(request, f'Você não tem permissão para acessar esta página. Requerido: {", ".join(group_names)}')
                return redirect('home')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

