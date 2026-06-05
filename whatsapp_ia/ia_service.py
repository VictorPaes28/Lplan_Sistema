from openai import OpenAI
from django.conf import settings

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


def chamar_openai(mensagem_usuario: str) -> str:
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            max_tokens=500,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': mensagem_usuario},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return MSG_ERRO_PADRAO
