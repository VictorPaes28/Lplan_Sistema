from functools import wraps
from django.shortcuts import redirect
from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse


def _is_api_request(request):
    """Requisições AJAX/API devem receber JSON em vez de redirect."""
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )


def login_required(view_func):
    """
    login_required que, para requisições AJAX/API, retorna JsonResponse 401 em vez de redirect.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if _is_api_request(request):
                return JsonResponse(
                    {'success': False, 'error': 'Você precisa estar autenticado.'},
                    status=401
                )
            return redirect(settings.LOGIN_URL)
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def require_group(*group_names):
    """
    Exige login e que o usuário pertença a **pelo menos um** dos grupos listados (*OR*)
    dentro do conjunto esperado para aquela área ou rota.

    Importante para quem autoriza vistas:
      - Liste **somente grupos válidos para aquele módulo/funcionalidade** (papéis alternativos
        do próprio recurso, ex.: três níveis TrackHub ou Diário vs Mapa no BI quando fizer sentido).
      - **Não** use como ``atalho`` um grupo de outro sistema só para liberar página
        de outra área sem que isso está documentado; quem opera em vários módulos deve ter
        **vários grupos atribuídos**, não papéis emprestados cruza-módulos.

    Superusuários sempre têm acesso (uso técnico).
    AJAX/API recebe JSON 401/403 em vez de redirect.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if _is_api_request(request):
                    return JsonResponse(
                        {'success': False, 'error': 'Você precisa estar autenticado.'},
                        status=401
                    )
                messages.error(request, 'Você precisa estar autenticado para acessar esta página.')
                return redirect(settings.LOGIN_URL)
            
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            if not request.user.groups.filter(name__in=group_names).exists():
                if _is_api_request(request):
                    return JsonResponse(
                        {'success': False, 'error': 'Você não tem permissão para esta ação.'},
                        status=403
                    )
                messages.error(request, 'Você não tem permissão para acessar esta página.')
                return redirect('select-system')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

