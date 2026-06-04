"""
Webhook WhatsApp Cloud API (Meta).

GET  /whatsapp/webhook/ — verificação (hub.mode, hub.verify_token, hub.challenge)
POST /whatsapp/webhook/ — recebimento de mensagens
"""
import json
import logging

import requests
from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from whatsapp_ia.models import IaErroLog, IaMensagemLog, UsuarioWhatsApp

logger = logging.getLogger(__name__)

WHATSAPP_API_VERSION = 'v19.0'
RESPOSTA_FIXA = 'Olá! Recebi sua mensagem. Em breve responderei.'
MSG_NAO_AUTORIZADO = (
    'Este número não está autorizado a consultar '
    'informações do sistema. Procure o administrador '
    'para liberar o acesso.'
)


def _enviar_mensagem_whatsapp(telefone, texto):
    """Envia mensagem de texto via Meta Graph API. Não propaga exceções."""
    phone_number_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '').strip()
    access_token = getattr(settings, 'WHATSAPP_ACCESS_TOKEN', '').strip()

    if not phone_number_id or not access_token:
        logger.error('WhatsApp: WHATSAPP_PHONE_NUMBER_ID ou WHATSAPP_ACCESS_TOKEN não configurados')
        return False

    url = (
        f'https://graph.facebook.com/{WHATSAPP_API_VERSION}/'
        f'{phone_number_id}/messages'
    )
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': telefone,
        'type': 'text',
        'text': {'body': texto},
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if not response.ok:
            logger.error(
                'WhatsApp API erro %s: %s',
                response.status_code,
                response.text[:500],
            )
            return False
        return True
    except requests.RequestException as exc:
        logger.exception('WhatsApp API falhou ao enviar mensagem: %s', exc)
        return False


def _extrair_mensagem_texto(payload):
    """
    Retorna (telefone, texto) ou (None, None) se não for mensagem de texto.
    Estrutura: entry[0].changes[0].value.messages[0]
    """
    try:
        entry = payload.get('entry') or []
        if not entry:
            return None, None
        changes = entry[0].get('changes') or []
        if not changes:
            return None, None
        value = changes[0].get('value') or {}
        messages = value.get('messages') or []
        if not messages:
            return None, None
        message = messages[0]
        if message.get('type') != 'text':
            return None, None
        telefone = message.get('from', '')
        texto = (message.get('text') or {}).get('body', '')
        if not telefone or not texto:
            return None, None
        return telefone, texto
    except (IndexError, KeyError, TypeError, AttributeError):
        return None, None


def _registrar_erro(erro, payload_resumido='', usuario=None):
    try:
        IaErroLog.objects.create(
            usuario=usuario,
            erro=str(erro)[:4000],
            payload_resumido=str(payload_resumido)[:4000],
        )
    except Exception:
        logger.exception('Falha ao gravar IaErroLog')


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def webhook(request):
    if request.method == 'GET':
        return _webhook_verificar(request)
    return _webhook_receber(request)


def _webhook_verificar(request):
    mode = request.GET.get('hub.mode', '')
    token = request.GET.get('hub.verify_token', '')
    challenge = request.GET.get('hub.challenge', '')
    verify_token = getattr(settings, 'WHATSAPP_VERIFY_TOKEN', '')

    if mode == 'subscribe' and token and token == verify_token:
        return HttpResponse(challenge, content_type='text/plain', status=200)
    return HttpResponseForbidden('Token de verificação inválido')


def _webhook_receber(request):
    usuario_whatsapp = None
    payload_raw = request.body.decode('utf-8', errors='replace')

    try:
        payload = json.loads(payload_raw) if payload_raw else {}
    except json.JSONDecodeError as exc:
        _registrar_erro(f'JSON inválido: {exc}', payload_resumido=payload_raw[:2000])
        return HttpResponse(status=200)

    try:
        telefone, texto = _extrair_mensagem_texto(payload)

        log = IaMensagemLog.objects.create(
            usuario=None,
            telefone=telefone or '',
            mensagem_recebida=json.dumps(payload, ensure_ascii=False),
        )

        if not telefone:
            return HttpResponse(status=200)

        usuario_wa = UsuarioWhatsApp.objects.filter(
            telefone=telefone, ativo=True
        ).first()
        if not usuario_wa and not telefone.startswith('+'):
            usuario_wa = UsuarioWhatsApp.objects.filter(
                telefone=f'+{telefone}', ativo=True
            ).first()

        if not usuario_wa:
            enviado = _enviar_mensagem_whatsapp(telefone, MSG_NAO_AUTORIZADO)
            log.resposta_enviada = MSG_NAO_AUTORIZADO
            log.status = 'nao_autorizado'
            log.save(update_fields=['resposta_enviada', 'status'])

            if not enviado:
                _registrar_erro(
                    'Falha ao enviar resposta de não autorizado via API Meta',
                    payload_resumido=f'telefone={telefone}',
                )
            return HttpResponse(status=200)

        usuario_whatsapp = usuario_wa
        enviado = _enviar_mensagem_whatsapp(telefone, RESPOSTA_FIXA)

        log.usuario = usuario_wa
        log.resposta_enviada = RESPOSTA_FIXA
        log.status = 'ok' if enviado else 'erro_envio'
        log.save(update_fields=['usuario', 'resposta_enviada', 'status'])

        if not enviado:
            _registrar_erro(
                'Falha ao enviar resposta via API Meta',
                payload_resumido=f'telefone={telefone}, texto={texto[:200]}',
                usuario=usuario_wa,
            )

    except Exception as exc:
        logger.exception('Erro no webhook WhatsApp: %s', exc)
        _registrar_erro(
            exc,
            payload_resumido=payload_raw[:2000],
            usuario=usuario_whatsapp,
        )

    return HttpResponse(status=200)
