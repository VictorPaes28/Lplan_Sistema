import json
import logging

from django.conf import settings
from openai import OpenAI

from whatsapp_ia.briefing import gerar_briefing_operacional
from whatsapp_ia.ia_functions import TOOLS, executar_funcao
from whatsapp_ia.models import IaMensagemLog
from whatsapp_ia.prompts import montar_system_prompt

logger = logging.getLogger(__name__)

MSG_ERRO_PADRAO = (
    'Não consegui processar sua consulta agora. '
    'Tente novamente ou acione o suporte.'
)

MAX_TOOL_ROUNDS = 8
MAX_TOKENS = 2000
HISTORICO_MENSAGENS = 10

_ACOES_PDF = frozenset({'enviar_pdf_rdo', 'enviar_pdf_pedido'})

_MSG_CONSOLIDAR_DEGRADADO = (
    'Limite de rodadas de consulta atingido. Consolide TODOS os dados '
    'já obtidos nas respostas das funções e responda ao usuário agora. '
    'Não invente dados que não foram retornados — indique claramente o '
    'que não foi possível verificar.'
)

_STATUS_HISTORICO_EXCLUIDOS = frozenset({'nao_autorizado', 'erro_envio'})


def _texto_usuario_de_log(mensagem_recebida: str) -> str:
    """Extrai texto do usuário — webhook JSON ou texto puro legado."""
    raw = (mensagem_recebida or '').strip()
    if not raw:
        return ''
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if not isinstance(payload, dict):
        return raw
    try:
        entry = payload.get('entry') or []
        if not entry:
            return ''
        changes = entry[0].get('changes') or []
        if not changes:
            return ''
        value = changes[0].get('value') or {}
        messages = value.get('messages') or []
        if not messages:
            return ''
        message = messages[0]
        if message.get('type') != 'text':
            return ''
        return (message.get('text') or {}).get('body', '').strip()
    except (IndexError, KeyError, TypeError, AttributeError):
        return ''


def _montar_historico_conversa(usuario_wa) -> list[dict]:
    """
    Últimas HISTORICO_MENSAGENS trocas (log) em ordem cronológica,
    como pares user/assistant para o contexto da OpenAI.
    """
    if not usuario_wa:
        return []

    logs = list(
        IaMensagemLog.objects.filter(usuario=usuario_wa)
        .exclude(status__in=_STATUS_HISTORICO_EXCLUIDOS)
        .exclude(resposta_enviada='')
        .order_by('-id')[:HISTORICO_MENSAGENS]
    )
    logs.reverse()

    historico = []
    for log in logs:
        texto_user = _texto_usuario_de_log(log.mensagem_recebida)
        resposta = (log.resposta_enviada or '').strip()
        if not texto_user or not resposta:
            continue
        historico.append({'role': 'user', 'content': texto_user})
        historico.append({'role': 'assistant', 'content': resposta})

    return historico


def _montar_messages_openai(
    system_prompt: str,
    mensagem_usuario: str,
    usuario_wa=None,
) -> list[dict]:
    messages = [{'role': 'system', 'content': system_prompt}]
    messages.extend(_montar_historico_conversa(usuario_wa))
    messages.append({'role': 'user', 'content': mensagem_usuario})
    return messages


def chamar_openai(mensagem_usuario: str, usuario_wa=None) -> str:
    """Compatível com chamadas existentes — retorna só o texto da resposta."""
    resposta, _meta = chamar_openai_com_meta(mensagem_usuario, usuario_wa=usuario_wa)
    return resposta


def chamar_openai_com_meta(
    mensagem_usuario: str,
    usuario_wa=None,
) -> tuple[str, dict]:
    """
    Orquestra briefing → prompt dinâmico → loop de tools → resposta final.

    Retorna (texto_resposta, meta) onde meta contém:
      - tool_rounds: int
      - functions_called: list[str]
      - degraded: bool (True se consolidou após esgotar rodadas)
    """
    meta = {
        'tool_rounds': 0,
        'functions_called': [],
        'degraded': False,
    }

    try:
        briefing = gerar_briefing_operacional(usuario_wa=usuario_wa)
        system_prompt = montar_system_prompt(briefing)

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        messages = _montar_messages_openai(
            system_prompt,
            mensagem_usuario,
            usuario_wa=usuario_wa,
        )

        for round_idx in range(MAX_TOOL_ROUNDS):
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                max_tokens=MAX_TOKENS,
                tools=TOOLS,
                tool_choice='auto',
                messages=messages,
            )

            msg = response.choices[0].message

            if not msg.tool_calls:
                texto = msg.content.strip() if msg.content else MSG_ERRO_PADRAO
                return texto, meta

            meta['tool_rounds'] = round_idx + 1
            messages.append(msg)

            for tool_call in msg.tool_calls:
                nome = tool_call.function.name
                meta['functions_called'].append(nome)

                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                resultado = executar_funcao(nome, args, usuario_wa=usuario_wa)

                try:
                    dados_acao = json.loads(resultado)
                    if dados_acao.get('acao') in _ACOES_PDF:
                        return resultado, meta
                except json.JSONDecodeError:
                    pass

                messages.append({
                    'role': 'tool',
                    'tool_call_id': tool_call.id,
                    'content': resultado,
                })

        # Fase 4: resposta degradada — consolida o que já foi coletado
        meta['degraded'] = True
        messages.append({
            'role': 'system',
            'content': _MSG_CONSOLIDAR_DEGRADADO,
        })

        response_final = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            max_tokens=MAX_TOKENS,
            messages=messages,
        )

        texto = response_final.choices[0].message.content
        if texto and texto.strip():
            return texto.strip(), meta

        logger.warning(
            'WhatsApp IA: rodadas esgotadas sem resposta (%s tools)',
            len(meta['functions_called']),
        )
        return MSG_ERRO_PADRAO, meta

    except Exception:
        logger.exception('WhatsApp IA: erro em chamar_openai_com_meta')
        return MSG_ERRO_PADRAO, meta
