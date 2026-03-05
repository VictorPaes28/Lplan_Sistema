"""
View customizada para falha de CSRF.
Quando a requisição é AJAX/API (X-Requested-With ou Accept: application/json),
retorna JSON 403 em vez da página HTML padrão do Django.

Endpoint GET /api/csrf-token/ para o frontend obter o token quando a meta tag estiver vazia (ex.: cache).
"""
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required


def csrf_failure_json(request, reason=''):
    """Chamada pelo Django quando a validação CSRF falha. Retorna JSON para requisições AJAX."""
    import logging
    logger = logging.getLogger('core')
    referer = request.META.get('HTTP_REFERER') or '(vazio)'
    origin = request.META.get('HTTP_ORIGIN') or '(vazio)'
    from django.conf import settings
    trusted = getattr(settings, 'CSRF_TRUSTED_ORIGINS', [])
    logger.warning(
        'CSRF 403: Referer=%s Origin=%s CSRF_TRUSTED_ORIGINS=%s path=%s',
        referer, origin, trusted, request.path
    )
    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )
    if is_ajax:
        return JsonResponse(
            {
                'success': False,
                'error': (
                    'Sessão expirada ou token de segurança inválido. '
                    'Recarregue a página e tente novamente.'
                ),
            },
            status=403,
            content_type='application/json',
        )
    # Fallback: usar a view padrão do Django (HTML)
    from django.views.csrf import csrf_failure as django_csrf_failure
    return django_csrf_failure(request, reason=reason)


@require_GET
@login_required
@ensure_csrf_cookie
def get_csrf_token(request):
    """Retorna o token CSRF em JSON para o frontend (Mapa de Suprimentos, etc.) quando a meta tag está vazia."""
    from django.middleware.csrf import get_token
    token = get_token(request)
    return JsonResponse({'csrfToken': token or ''})
