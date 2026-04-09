"""
Handlers HTTP customizados (ver handler400 em lplan_central/urls).
"""
import logging

from django.core.exceptions import RequestDataTooBig, TooManyFieldsSent
from django.http import HttpResponse, JsonResponse
from django.views.defaults import bad_request as django_default_bad_request

logger = logging.getLogger(__name__)


def _wants_json(request):
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )


def bad_request(request, exception, template_name='400.html'):
    """
    400 com payload claro quando o Django rejeita o corpo do POST (tamanho ou nº de campos).
    Nginx 413 continua sendo tratado no proxy (ver deploy/nginx-upload-limits.conf).
    """
    if isinstance(exception, RequestDataTooBig):
        code = 'UPLOAD_BODY_TOO_LARGE'
        message = (
            'O tamanho total do envio excede o limite permitido pelo servidor. '
            'Reduza o tamanho dos anexos ou envie em etapas.'
        )
        logger.warning(
            'HTTP 400 %s path=%s method=%s',
            code,
            request.path,
            request.method,
        )
        payload = {'success': False, 'code': code, 'message': message}
        if _wants_json(request):
            return JsonResponse(payload, status=400)
        html = (
            f'<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">'
            f'<title>Envio muito grande</title></head><body>'
            f'<h1>Dados enviados em excesso</h1>'
            f'<p>{message}</p>'
            f'<p><small>Código: {code}</small></p>'
            f'</body></html>'
        )
        return HttpResponse(html, status=400, content_type='text/html; charset=utf-8')

    if isinstance(exception, TooManyFieldsSent):
        code = 'FORM_TOO_MANY_FIELDS'
        message = (
            'Este formulário enviou mais campos do que o servidor aceita de uma vez. '
            'Recarregue a página e tente novamente; se persistir, avise o suporte.'
        )
        logger.warning(
            'HTTP 400 %s path=%s method=%s',
            code,
            request.path,
            request.method,
        )
        payload = {'success': False, 'code': code, 'message': message}
        if _wants_json(request):
            return JsonResponse(payload, status=400)
        html = (
            f'<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">'
            f'<title>Formulário inválido</title></head><body>'
            f'<h1>Muitos campos no envio</h1>'
            f'<p>{message}</p>'
            f'<p><small>Código: {code}</small></p>'
            f'</body></html>'
        )
        return HttpResponse(html, status=400, content_type='text/html; charset=utf-8')

    return django_default_bad_request(request, exception, template_name)
