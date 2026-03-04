"""
View customizada para falha de CSRF.
Quando a requisição é AJAX/API (X-Requested-With ou Accept: application/json),
retorna JSON 403 em vez da página HTML padrão do Django.
"""
from django.http import JsonResponse


def csrf_failure_json(request, reason=''):
    """Chamada pelo Django quando a validação CSRF falha. Retorna JSON para requisições AJAX."""
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
