import json

from django.conf import settings
from openai import OpenAI

from whatsapp_ia.ia_functions import TOOLS, executar_funcao

SYSTEM_PROMPT = """
Você é a assistente operacional da Lplan no WhatsApp.
Responda de forma objetiva, curta e útil.
Você só pode responder com base nos dados fornecidos
pelas funções do sistema.
Nunca invente números, status, obras, datas, PDFs ou
responsáveis.
Quando faltar informação essencial, pergunte apenas
o necessário.
Quando o usuário não tiver permissão, informe de forma
educada que a consulta não está autorizada.
Ações críticas como aprovar, excluir, alterar status
ou modificar dados não são permitidas neste MVP.
"""

MSG_ERRO_PADRAO = (
    'Não consegui processar sua consulta agora. '
    'Tente novamente ou acione o suporte.'
)


def chamar_openai(mensagem_usuario: str, usuario_wa=None) -> str:
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        messages = [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': mensagem_usuario},
        ]

        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            max_tokens=1000,
            tools=TOOLS,
            tool_choice='auto',
            messages=messages,
        )

        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content.strip() if msg.content else MSG_ERRO_PADRAO

        messages.append(msg)
        for tool_call in msg.tool_calls:
            nome = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}
            resultado = executar_funcao(nome, args, usuario_wa=usuario_wa)
            messages.append({
                'role': 'tool',
                'tool_call_id': tool_call.id,
                'content': resultado,
            })

        response2 = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            max_tokens=1000,
            messages=messages,
        )

        return response2.choices[0].message.content.strip()

    except Exception:
        return MSG_ERRO_PADRAO
