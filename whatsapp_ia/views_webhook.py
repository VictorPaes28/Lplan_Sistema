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

from whatsapp_ia.ia_service import MSG_ERRO_PADRAO, chamar_openai
from whatsapp_ia.models import IaErroLog, IaMensagemLog, UsuarioWhatsApp

logger = logging.getLogger(__name__)

WHATSAPP_API_VERSION = 'v21.0'
MSG_NAO_AUTORIZADO = (
    'Este número não está autorizado a consultar '
    'informações do sistema. Procure o administrador '
    'para liberar o acesso.'
)


def normalizar_telefone(telefone: str) -> list[str]:
    """
    Retorna variantes do número para busca no banco.
    A Meta omite o '+' e às vezes o 9º dígito de celulares BR.
    """
    variantes = set()

    # Garante que tem só dígitos para manipular
    numero = telefone.lstrip('+')

    # Variante com + na frente
    variantes.add(f'+{numero}')

    # Se for número brasileiro (começa com 55) e tiver 12 dígitos
    # (55 + DDD 2 dígitos + número 8 dígitos = sem o 9)
    # inserir o 9 após o DDD
    if numero.startswith('55') and len(numero) == 12:
        ddd = numero[2:4]
        restante = numero[4:]
        variantes.add(f'+55{ddd}9{restante}')

    # Se tiver 13 dígitos (já tem o 9), também tentar sem o 9
    if numero.startswith('55') and len(numero) == 13:
        ddd = numero[2:4]
        restante = numero[5:]  # pula o 9
        variantes.add(f'+55{ddd}{restante}')

    return list(variantes)


def telefone_para_envio(telefone: str) -> str:
    numero = telefone.lstrip('+')
    if numero.startswith('55') and len(numero) == 12:
        ddd = numero[2:4]
        restante = numero[4:]
        return f'55{ddd}9{restante}'
    return numero


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
        'to': telefone_para_envio(telefone),
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


def _enviar_documento_whatsapp(
    telefone: str, pdf_bytes, filename: str, caption: str = ''
) -> bool:
    """
    Envia documento PDF pelo WhatsApp via Meta API.
    Salva temporariamente em MEDIA_ROOT/pdfs/whatsapp/,
    envia via URL pública e agenda remoção.
    """
    import threading
    import time
    import uuid
    from pathlib import Path

    try:
        pasta = Path(settings.MEDIA_ROOT) / 'pdfs' / 'whatsapp'
        pasta.mkdir(parents=True, exist_ok=True)
        nome_arquivo = f'{uuid.uuid4().hex}_{filename}'
        caminho = pasta / nome_arquivo

        with open(caminho, 'wb') as f:
            if hasattr(pdf_bytes, 'read'):
                f.write(pdf_bytes.read())
            else:
                f.write(pdf_bytes)

        base_url = getattr(
            settings, 'WHATSAPP_BASE_URL', 'https://sistema.lplan.com.br'
        ).rstrip('/')
        media_url = settings.MEDIA_URL
        if not media_url.endswith('/'):
            media_url += '/'
        url_publica = f'{base_url}{media_url}pdfs/whatsapp/{nome_arquivo}'

        token = getattr(settings, 'WHATSAPP_ACCESS_TOKEN', '').strip()
        phone_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '').strip()
        if not token or not phone_id:
            logger.error(
                'WhatsApp: WHATSAPP_ACCESS_TOKEN ou '
                'WHATSAPP_PHONE_NUMBER_ID não configurados'
            )
            return False

        url = (
            f'https://graph.facebook.com/{WHATSAPP_API_VERSION}'
            f'/{phone_id}/messages'
        )
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': telefone_para_envio(telefone),
            'type': 'document',
            'document': {
                'link': url_publica,
                'filename': filename,
                'caption': caption,
            },
        }
        response = requests.post(
            url, json=payload, headers=headers, timeout=30
        )
        sucesso = response.status_code == 200
        if not sucesso:
            logger.error(
                'WhatsApp API erro ao enviar documento %s: %s',
                response.status_code,
                response.text[:500],
            )

        def remover():
            time.sleep(300)
            try:
                caminho.unlink(missing_ok=True)
            except Exception:
                pass

        threading.Thread(target=remover, daemon=True).start()

        return sucesso

    except Exception as exc:
        logger.exception('Erro ao enviar documento WhatsApp: %s', exc)
        return False


def _processar_acao_pdf(
    telefone: str, resposta_ia: str
) -> tuple[bool, str]:
    """
    Verifica se a IA retornou uma ação de PDF.
    Se sim, gera e envia o PDF e retorna (True, texto_confirmacao).
    Se não, retorna (False, resposta_ia).
    """
    try:
        dados = json.loads(resposta_ia)
        if dados.get('acao') == 'enviar_pdf_rdo':
            diary_id = dados['diary_id']
            obra = dados['obra']
            data = dados['data']

            from core.models import ConstructionDiary
            from core.utils.pdf_generator import PDFGenerator, get_rdo_pdf_filename

            diary = ConstructionDiary.objects.select_related(
                'project'
            ).get(id=diary_id)

            pdf_buffer = PDFGenerator.generate_diary_pdf(
                diary_id, pdf_type='normal'
            )
            if not pdf_buffer:
                return False, (
                    f'Não foi possível gerar o PDF do RDO '
                    f'da obra {obra} em {data}.'
                )

            filename = get_rdo_pdf_filename(diary.project, diary.date)
            caption = f'RDO — {obra} — {data}'

            enviado = _enviar_documento_whatsapp(
                telefone, pdf_buffer, filename, caption
            )
            if enviado:
                return True, f'PDF do RDO enviado: {obra} — {data}'
            return False, (
                'Não consegui enviar o PDF agora. '
                'Tente novamente.'
            )
    except (json.JSONDecodeError, KeyError, Exception):
        pass
    return False, resposta_ia


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

        variantes = normalizar_telefone(telefone)
        usuario_wa = UsuarioWhatsApp.objects.filter(
            telefone__in=variantes, ativo=True
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
        try:
            resposta = chamar_openai(texto, usuario_wa=usuario_wa)
        except Exception as exc:
            logger.exception('Erro ao chamar OpenAI: %s', exc)
            _registrar_erro(
                exc,
                payload_resumido=f'telefone={telefone}, texto={texto[:200]}',
                usuario=usuario_wa,
            )
            resposta = MSG_ERRO_PADRAO

        eh_pdf, resposta_final = _processar_acao_pdf(telefone, resposta)
        if eh_pdf:
            log.usuario = usuario_wa
            log.intencao_detectada = 'enviar_pdf_rdo'
            log.funcao_chamada = 'enviar_pdf_rdo'
            log.resposta_enviada = resposta_final
            log.status = 'ok'
            log.save(
                update_fields=[
                    'usuario',
                    'intencao_detectada',
                    'funcao_chamada',
                    'resposta_enviada',
                    'status',
                ]
            )
            return HttpResponse(status=200)

        enviado = _enviar_mensagem_whatsapp(telefone, resposta_final)

        log.usuario = usuario_wa
        log.intencao_detectada = 'resposta_direta'
        log.funcao_chamada = 'chamar_openai'
        log.resposta_enviada = resposta_final
        log.status = 'ok' if enviado else 'erro_envio'
        log.save(
            update_fields=[
                'usuario',
                'intencao_detectada',
                'funcao_chamada',
                'resposta_enviada',
                'status',
            ]
        )

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
