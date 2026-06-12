"""Notificações RH/DP via WhatsApp (reutiliza whatsapp_ia)."""
from __future__ import annotations

import logging

from django.utils import timezone

from whatsapp_ia.views_webhook import _enviar_mensagem_whatsapp

from .alerts import AlertaRH, gerar_alertas

logger = logging.getLogger(__name__)

_URGENCIA_WHATSAPP = {
    'red': 'critico',
    'yellow': 'alto',
    'green': 'baixo',
}

_URGENCIA_EMOJI = {
    'critico': '🔴',
    'alto': '🟠',
    'medio': '🟡',
    'baixo': '🟢',
}


def _whatsapp_configurado() -> bool:
    from django.conf import settings

    phone_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '').strip()
    token = getattr(settings, 'WHATSAPP_ACCESS_TOKEN', '').strip()
    return bool(phone_id and token)


def _enviar_whatsapp_se_configurado(telefone: str, texto: str) -> bool:
    if not telefone:
        return False
    if not _whatsapp_configurado():
        logger.debug('RH: WhatsApp não configurado — envio ignorado para %s', telefone)
        return False
    return _enviar_mensagem_whatsapp(telefone, texto)


def _formatar_alerta_whatsapp(alerta: AlertaRH) -> str:
    chave = _URGENCIA_WHATSAPP.get(alerta.urgencia, 'baixo')
    urgencia_emoji = _URGENCIA_EMOJI.get(chave, '⚪')
    return (
        f'{urgencia_emoji} *{alerta.tipo}*\n'
        f'👤 {alerta.colaborador_nome}\n'
        f'📋 {alerta.detalhe}\n'
        f'📅 Prazo: {alerta.prazo or "Sem prazo"}'
    )


def enviar_resumo_alertas_whatsapp(telefone: str) -> dict:
    """
    Gera resumo dos alertas críticos e envia via WhatsApp.
    Retorna dict com total enviado e erros.
    """
    alertas = gerar_alertas()
    criticos = [a for a in alertas if a.urgencia in ('red', 'yellow')]

    if not criticos:
        msg = (
            '✅ *RH/DP — Sem alertas críticos hoje*\n'
            f'Data: {timezone.localdate().strftime("%d/%m/%Y")}\n'
            'Todos os documentos e prazos estão em dia.'
        )
        sucesso = _enviar_whatsapp_se_configurado(telefone, msg)
        return {'enviado': sucesso, 'alertas': 0}

    linhas = [
        f'⚠️ *RH/DP — {len(criticos)} alerta(s) crítico(s)*',
        f'📅 {timezone.localdate().strftime("%d/%m/%Y")}',
        '',
    ]
    for alerta in criticos[:10]:
        linhas.append(_formatar_alerta_whatsapp(alerta))
        linhas.append('')

    if len(criticos) > 10:
        linhas.append(
            f'_...e mais {len(criticos) - 10} alertas. '
            f'Acesse o sistema para ver todos._'
        )

    msg = '\n'.join(linhas)
    sucesso = _enviar_whatsapp_se_configurado(telefone, msg)
    return {'enviado': sucesso, 'alertas': len(criticos)}


def enviar_alerta_vencimento_individual(
    telefone: str,
    colaborador_nome: str,
    documento_nome: str,
    dias: int,
) -> bool:
    """Envia alerta de vencimento de um documento específico."""
    if dias < 0:
        msg = (
            f'🔴 *Documento vencido — RH/DP*\n'
            f'👤 {colaborador_nome}\n'
            f'📋 {documento_nome}\n'
            f'⚠️ Vencido há {abs(dias)} dia(s). '
            f'Providenciar renovação urgente.'
        )
    else:
        msg = (
            f'🟡 *Documento vencendo — RH/DP*\n'
            f'👤 {colaborador_nome}\n'
            f'📋 {documento_nome}\n'
            f'📅 Vence em {dias} dia(s). '
            f'Providenciar renovação.'
        )
    return _enviar_whatsapp_se_configurado(telefone, msg)


def notificar_rh_requisicao_reprovada(colaborador) -> bool:
    """Notifica o RH que criou a requisição sobre reprovação pelo gestor."""
    from django.conf import settings
    from django.core.mail import send_mail

    destinatario = None
    if colaborador.requisicao_criada_por_id:
        destinatario = getattr(colaborador.requisicao_criada_por, 'email', None)
    remetente = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
    if not destinatario or not remetente:
        logger.warning(
            'RH: e-mail de reprovação não enviado (destinatário ou remetente ausente) '
            '— colaborador pk=%s',
            colaborador.pk,
        )
        return False
    gestor = colaborador.gestor_aprovador or 'Gestor responsável'
    motivo = colaborador.requisicao_motivo_reprovacao or 'Sem motivo informado.'
    assunto = f'Lplan — Requisição reprovada: {colaborador.nome}'
    corpo = (
        f'A requisição de admissão de *{colaborador.nome}* foi reprovada por {gestor}.\n\n'
        f'Motivo:\n{motivo}\n\n'
        f'Acesse o fluxo de Admissão no sistema para corrigir e reenviar a requisição.'
    )
    try:
        send_mail(assunto, corpo, remetente, [destinatario], fail_silently=False)
        return True
    except Exception as exc:
        logger.exception('RH: erro ao enviar e-mail de reprovação: %s', exc)
        return False


def notificar_gestor_nova_requisicao(gestor_user, colaborador) -> bool:
    """Notifica o gestor responsável sobre nova requisição de admissão pendente."""
    perfil = getattr(gestor_user, 'perfil', None)
    telefone = getattr(perfil, 'telefone', None) if perfil else None
    if not telefone:
        logger.warning(
            'RH: gestor %s sem telefone no perfil — WhatsApp não enviado',
            gestor_user.username,
        )
        return False
    if not _whatsapp_configurado():
        logger.warning('RH: WhatsApp não configurado — gestor %s não notificado', gestor_user.username)
        return False
    obras = ', '.join(colaborador.obras.values_list('nome', flat=True)[:3]) or '—'
    msg = (
        f'📋 *Nova requisição de admissão para aprovar*\n'
        f'👤 Candidato: {colaborador.nome}\n'
        f'💼 Cargo: {colaborador.cargo}\n'
        f'🏗️ Obra(s): {obras}\n'
        f'Acesse o sistema RH para aprovar a requisição.'
    )
    return _enviar_whatsapp_se_configurado(telefone, msg)


def notificar_nova_admissao(telefone: str, colaborador_nome: str, cargo: str) -> bool:
    """Notifica RH sobre nova requisição de admissão."""
    if not telefone:
        return False
    if not _whatsapp_configurado():
        logger.warning('RH: WhatsApp não configurado — RH_WHATSAPP_NOTIFICACAO ignorado')
        return False
    msg = (
        f'📋 *Nova requisição de admissão — RH/DP*\n'
        f'👤 {colaborador_nome}\n'
        f'💼 Cargo: {cargo}\n'
        f'Acesse o sistema para iniciar o processo.'
    )
    return _enviar_whatsapp_se_configurado(telefone, msg)


def _montar_link_portal(token: str, base_url: str | None = None) -> str:
    from django.conf import settings

    # Em produção, definir SITE_URL no .env (ex.: https://sistema.lplan.com.br)
    base = (base_url or getattr(settings, 'SITE_URL', '') or 'https://sistema.lplan.com.br').rstrip('/')
    return f'{base}/rh/portal/{token}/'


def enviar_link_portal_email(
    email: str,
    colaborador_nome: str,
    token: str,
    base_url: str | None = None,
) -> bool:
    """Envia link do portal de documentos por e-mail (texto + HTML)."""
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string

    destino = (email or '').strip()
    if not destino:
        return False
    link = _montar_link_portal(token, base_url)
    assunto = f'Lplan — Documentos para admissão de {colaborador_nome}'
    ctx = {
        'nome': colaborador_nome,
        'link': link,
    }
    corpo_txt = (
        f'Olá, {colaborador_nome}!\n\n'
        f'Sua admissão na Lplan foi iniciada.\n\n'
        f'Envie seus documentos pelo link:\n{link}\n\n'
        f'O link é válido por 30 dias.\n'
        f'Dúvidas: rh@lplan.com.br'
    )
    corpo_html = render_to_string(
        'recursos_humanos/emails/link_portal_candidato.html',
        ctx,
    )
    remetente = getattr(settings, 'DEFAULT_FROM_EMAIL', 'sistema@lplan.com.br')
    try:
        msg = EmailMultiAlternatives(assunto, corpo_txt, remetente, [destino])
        msg.attach_alternative(corpo_html, 'text/html')
        msg.send()
        return True
    except Exception as exc:
        logger.exception('RH: erro ao enviar e-mail do portal: %s', exc)
        return False


def enviar_link_portal_candidato(colaborador) -> dict:
    """Envia o link do portal ao candidato por e-mail (obrigatório) e WhatsApp (se houver telefone)."""
    token = colaborador.token_portal
    if not token:
        return {'email': False, 'whatsapp': False}
    email_ok = False
    if colaborador.email:
        email_ok = enviar_link_portal_email(
            colaborador.email,
            colaborador.nome,
            token,
        )
    whatsapp_ok = False
    if colaborador.telefone:
        whatsapp_ok = enviar_link_portal_whatsapp(
            colaborador.telefone,
            colaborador.nome,
            token,
        )
    return {'email': email_ok, 'whatsapp': whatsapp_ok}


def enviar_link_portal_whatsapp(
    telefone: str,
    colaborador_nome: str,
    token: str,
    base_url: str | None = None,
) -> bool:
    if not telefone:
        return False
    if not _whatsapp_configurado():
        logger.debug('RH: WhatsApp não configurado — link do portal não enviado por WhatsApp')
        return False
    link = _montar_link_portal(token, base_url)
    msg = (
        f'Olá, *{colaborador_nome}*! 👋\n\n'
        f'Sua admissão na *Lplan* foi iniciada.\n\n'
        f'📋 Envie seus documentos pelo link abaixo:\n'
        f'{link}\n\n'
        f'⏰ O link é válido por 30 dias.\n'
        f'Em caso de dúvidas, entre em contato '
        f'com o RH.'
    )
    return _enviar_whatsapp_se_configurado(telefone, msg)
