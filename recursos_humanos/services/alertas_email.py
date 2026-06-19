"""Envio de e-mails agrupados de alertas RH para os responsáveis configurados."""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils import timezone

from recursos_humanos.services.alertas_config import obter_configuracao_alertas

logger = logging.getLogger(__name__)

TIPOS_ALERTA_EMAIL = frozenset({
    'Documento vencendo',
    'Documento vencido',
    'Prazo de contrato',
})


def _montar_corpo_email(alertas) -> str:
    hoje = timezone.localdate().strftime('%d/%m/%Y')
    linhas = [
        f'Alertas RH — resumo de {hoje}',
        '',
        'Os itens abaixo requerem atenção:',
        '',
    ]
    for alerta in alertas:
        linhas.append(
            f'- {alerta.titulo or alerta.detalhe} ({alerta.colaborador_nome}) — '
            f'{alerta.prazo}'
        )
    linhas.extend(['', 'Acesse o módulo DP/RH > Prazos e Alertas para mais detalhes.'])
    return '\n'.join(linhas)


def enviar_emails_alertas_diarios(alertas) -> int:
    """Envia um e-mail por responsável com todos os alertas do dia (máx. 1x/dia cada)."""
    config = obter_configuracao_alertas()
    if not config.notificar_email:
        return 0

    relevantes = [a for a in alertas if a.tipo in TIPOS_ALERTA_EMAIL]
    if not relevantes:
        return 0

    corpo = _montar_corpo_email(relevantes)
    assunto = f'[LPLAN RH] Alertas do dia {timezone.localdate():%d/%m/%Y}'
    hoje = timezone.localdate().isoformat()
    enviados = 0

    for user in config.responsaveis.filter(is_active=True):
        email = (user.email or '').strip()
        if not email:
            continue
        cache_key = f'rh:alertas_email:{user.pk}:{hoje}'
        if cache.get(cache_key):
            continue
        try:
            send_mail(
                assunto,
                corpo,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            cache.set(cache_key, True, timeout=60 * 60 * 25)
            enviados += 1
        except Exception:
            logger.exception('Falha ao enviar e-mail de alertas RH para %s', email)

    return enviados
