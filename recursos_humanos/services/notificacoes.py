"""Notificações RH/DP via WhatsApp (reutiliza whatsapp_ia)."""
from __future__ import annotations

import logging

from django.utils import timezone

from whatsapp_ia.views_webhook import _enviar_mensagem_whatsapp

from .alerts import AlertaRH, gerar_alertas

logger = logging.getLogger(__name__)


def envio_portal_candidato_ativo() -> bool:
    """
    Envio de link/PIN do portal ao colaborador por e-mail ou WhatsApp.
    Desligado por padrão — o gestor preenche no sistema.
    Para reativar no futuro: RH_ENVIO_PORTAL_CANDIDATO_ATIVO=True no settings/.env
    """
    from django.conf import settings

    return bool(getattr(settings, 'RH_ENVIO_PORTAL_CANDIDATO_ATIVO', False))

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
    """Notifica o responsável que criou a requisição sobre a reprovação."""
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
    reprovador = colaborador.gestor_aprovador or 'Responsável pela admissão'
    motivo = colaborador.requisicao_motivo_reprovacao or 'Sem motivo informado.'
    assunto = f'Lplan — Requisição reprovada: {colaborador.nome}'
    corpo = (
        f'A requisição de admissão de *{colaborador.nome}* foi reprovada por {reprovador}.\n\n'
        f'Motivo:\n{motivo}\n\n'
        f'Acesse o fluxo de Admissão no sistema para corrigir e reenviar a requisição.'
    )
    try:
        send_mail(assunto, corpo, remetente, [destinatario], fail_silently=False)
        return True
    except Exception as exc:
        logger.exception('RH: erro ao enviar e-mail de reprovação: %s', exc)
        return False


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


def _build_email_logo_url(base_url: str | None = None) -> str:
    """URL absoluta da logo LPLAN (fallback quando não há arquivo local)."""
    from django.conf import settings

    base = (base_url or getattr(settings, 'SITE_URL', '') or 'https://sistema.lplan.com.br').rstrip('/')
    return f'{base}/static/core/images/lpla-logo-pdf-transparent.png'


def _anexar_logo_inline_email(msg) -> str | None:
    """Embute a logo no e-mail (funciona sem SITE_URL público). Retorna src cid ou None."""
    from email.mime.image import MIMEImage

    from django.contrib.staticfiles import finders

    for rel_path in (
        'core/images/lpla-logo-pdf-transparent.png',
        'core/images/lplan-logo2.png',
    ):
        path = finders.find(rel_path)
        if not path:
            continue
        try:
            with open(path, 'rb') as fp:
                mime_img = MIMEImage(fp.read())
            mime_img.add_header('Content-ID', '<lplan-logo>')
            mime_img.add_header('Content-Disposition', 'inline', filename='lplan-logo.png')
            msg.attach(mime_img)
            return 'cid:lplan-logo'
        except OSError:
            logger.warning('RH: não foi possível ler logo para e-mail: %s', path)
    return None


def _formatar_linhas_pendencias_coleta(pendencias: list[dict]) -> list[str]:
    linhas: list[str] = []
    dados = [p['label'] for p in pendencias if p.get('tipo') == 'dado']
    docs = [p for p in pendencias if p.get('tipo') == 'documento']
    if dados:
        linhas.append('Dados pessoais:')
        linhas.extend(f'- {nome}' for nome in dados)
    if docs:
        if linhas:
            linhas.append('')
        linhas.append('Documentos:')
        for doc in docs:
            linha = f'- {doc["label"]}'
            if doc.get('detalhe'):
                linha += f' ({doc["detalhe"]})'
            linhas.append(linha)
    return linhas


def _formatar_linhas_pendencias_whatsapp(pendencias: list[dict]) -> str:
    linhas = _formatar_linhas_pendencias_coleta(pendencias)
    if not linhas:
        return ''
    return '\n'.join(linhas)


def _bloco_pin_email(portal_pin: str | None) -> str:
    if not portal_pin:
        return (
            '\nUtilize o código de acesso enviado anteriormente junto com este link.\n'
        )
    return (
        f'\nCódigo de acesso ao portal: {portal_pin}\n'
        f'Na primeira tela, informe este código de 6 dígitos para continuar.\n'
        f'Não compartilhe o código com terceiros.\n'
    )


def _bloco_pin_whatsapp(portal_pin: str | None) -> str:
    if portal_pin:
        return (
            f'\n🔐 *Código de acesso:* {portal_pin}\n'
            f'Na primeira tela, informe este código de 6 dígitos.\n'
        )
    return (
        '\n🔐 Use o código de 6 dígitos enviado na mensagem anterior (e-mail ou WhatsApp).\n'
    )


def _montar_texto_email_portal(
    colaborador_nome: str,
    link: str,
    *,
    reenvio: bool = False,
    documento_nome: str = '',
    motivo_texto: str = '',
    lembrete: bool = False,
    documentos_pendentes: list[str] | None = None,
    solicitacao_pendencias: bool = False,
    pendencias_coleta: list[dict] | None = None,
    primeiro_acesso: bool = False,
    portal_pin: str | None = None,
) -> str:
    pin_txt = _bloco_pin_email(portal_pin)
    pendentes = documentos_pendentes or []
    itens_coleta = pendencias_coleta or []
    if solicitacao_pendencias and itens_coleta:
        corpo_lista = '\n'.join(_formatar_linhas_pendencias_coleta(itens_coleta))
        intro = 'Identificamos pendências no seu cadastro de admissão:'
    elif primeiro_acesso and itens_coleta:
        corpo_lista = '\n'.join(_formatar_linhas_pendencias_coleta(itens_coleta))
        intro = 'Sua admissão na LPLAN foi iniciada. Para começar, complete no portal:'
    elif lembrete and pendentes:
        corpo_lista = '\n'.join(f'- {nome}' for nome in pendentes)
        intro = 'Lembramos que ainda há documentos pendentes na sua admissão:'
    elif reenvio and documento_nome:
        return (
            f'Olá, {colaborador_nome}!\n\n'
            f'O documento "{documento_nome}" {motivo_texto} e precisa ser reenviado.\n'
            f'No portal, somente este documento estará liberado.\n\n'
            f'Acesse o portal pelo link:\n{link}\n'
            f'{pin_txt}\n'
            f'O link é válido por 30 dias.\n'
            f'Dúvidas: rh@lplan.com.br'
        )
    else:
        return (
            f'Olá, {colaborador_nome}!\n\n'
            f'Sua admissão na LPLAN foi iniciada.\n\n'
            f'Acesse o portal pelo link:\n{link}\n'
            f'{pin_txt}\n'
            f'O link é válido por 30 dias.\n'
            f'Dúvidas: rh@lplan.com.br'
        )
    return (
        f'Olá, {colaborador_nome}!\n\n'
        f'{intro}\n\n'
        f'{corpo_lista}\n\n'
        f'Acesse o portal pelo link:\n{link}\n'
        f'{pin_txt}\n'
        f'O link é válido por 30 dias.\n'
        f'Dúvidas: rh@lplan.com.br'
    )


def _montar_texto_whatsapp_portal(
    colaborador_nome: str,
    link: str,
    *,
    modo: str = 'inicial',
    documento_nome: str = '',
    motivo_texto: str = '',
    pendencias_coleta: list[dict] | None = None,
    documentos_pendentes: list[str] | None = None,
    portal_pin: str | None = None,
) -> str:
    pin_txt = _bloco_pin_whatsapp(portal_pin)
    pendencias = pendencias_coleta or []
    pendentes = documentos_pendentes or []
    if modo == 'reenvio' and documento_nome:
        return (
            f'Olá, *{colaborador_nome}*!\n\n'
            f'O documento *{documento_nome}* {motivo_texto} e precisa ser reenviado.\n'
            f'No portal, somente este item estará liberado.\n\n'
            f'🔗 {link}'
            f'{pin_txt}\n'
            f'⏰ Link válido por 30 dias.'
        )
    if modo in ('pendencias', 'inicial') and pendencias:
        lista = _formatar_linhas_pendencias_whatsapp(pendencias)
        titulo = (
            'Complete as pendências abaixo no portal:'
            if modo == 'pendencias'
            else 'Sua admissão na *LPLAN* foi iniciada. Envie no portal:'
        )
        return (
            f'Olá, *{colaborador_nome}*!\n\n'
            f'{titulo}\n\n'
            f'{lista}\n\n'
            f'🔗 {link}'
            f'{pin_txt}\n'
            f'⏰ Link válido por 30 dias.'
        )
    if modo == 'lembrete' and pendentes:
        lista = '\n'.join(f'• {nome}' for nome in pendentes)
        return (
            f'Olá, *{colaborador_nome}*!\n\n'
            f'Lembrete: ainda faltam documentos na admissão:\n\n'
            f'{lista}\n\n'
            f'🔗 {link}'
            f'{pin_txt}\n'
            f'⏰ Link válido por 30 dias.'
        )
    return (
        f'Olá, *{colaborador_nome}*!\n\n'
        f'Sua admissão na *LPLAN* foi iniciada.\n\n'
        f'🔗 Acesse o portal:\n{link}'
        f'{pin_txt}\n'
        f'⏰ Link válido por 30 dias.'
    )


def enviar_link_portal_email(
    email: str,
    colaborador_nome: str,
    token: str,
    base_url: str | None = None,
    *,
    reenvio: bool = False,
    documento_nome: str = '',
    motivo_texto: str = '',
    lembrete: bool = False,
    documentos_pendentes: list[str] | None = None,
    solicitacao_pendencias: bool = False,
    pendencias_coleta: list[dict] | None = None,
    primeiro_acesso: bool = False,
    portal_pin: str | None = None,
) -> bool:
    """Envia link do portal de documentos por e-mail (texto + HTML)."""
    if not envio_portal_candidato_ativo():
        logger.debug('RH: envio de e-mail do portal desativado (RH_ENVIO_PORTAL_CANDIDATO_ATIVO)')
        return False
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string

    destino = (email or '').strip()
    if not destino:
        return False
    link = _montar_link_portal(token, base_url)
    logo_url = _build_email_logo_url(base_url)
    pendentes = documentos_pendentes or []
    itens_coleta = pendencias_coleta or []
    if solicitacao_pendencias and itens_coleta:
        assunto = f'Lplan — Complete suas pendências — {colaborador_nome}'
    elif primeiro_acesso and itens_coleta:
        assunto = f'Lplan — Início da admissão — {colaborador_nome}'
    elif lembrete and pendentes:
        assunto = f'Lplan — Lembrete: documentos pendentes — {colaborador_nome}'
    elif reenvio and documento_nome:
        assunto = f'Lplan — Reenvio de documento: {documento_nome}'
    else:
        assunto = f'Lplan — Documentos para admissão de {colaborador_nome}'
    ctx = {
        'nome': colaborador_nome,
        'link': link,
        'logo_url': logo_url,
        'logo_cid': None,
        'reenvio': reenvio,
        'documento_nome': documento_nome,
        'motivo_texto': motivo_texto,
        'lembrete': lembrete,
        'documentos_pendentes': pendentes,
        'solicitacao_pendencias': solicitacao_pendencias,
        'pendencias_coleta': itens_coleta,
        'primeiro_acesso': primeiro_acesso,
        'portal_pin': portal_pin,
    }
    corpo_txt = _montar_texto_email_portal(
        colaborador_nome,
        link,
        reenvio=reenvio,
        documento_nome=documento_nome,
        motivo_texto=motivo_texto,
        lembrete=lembrete,
        documentos_pendentes=pendentes,
        solicitacao_pendencias=solicitacao_pendencias,
        pendencias_coleta=itens_coleta,
        primeiro_acesso=primeiro_acesso,
        portal_pin=portal_pin,
    )
    remetente = getattr(settings, 'DEFAULT_FROM_EMAIL', 'sistema@lplan.com.br')
    try:
        msg = EmailMultiAlternatives(assunto, corpo_txt, remetente, [destino])
        logo_cid = _anexar_logo_inline_email(msg)
        ctx['logo_cid'] = logo_cid or logo_url
        corpo_html = render_to_string(
            'recursos_humanos/emails/link_portal_candidato.html',
            ctx,
        )
        msg.attach_alternative(corpo_html, 'text/html')
        msg.send()
        if portal_pin:
            logger.info(
                'RH portal — e-mail para %s | link=%s | PIN=%s',
                destino,
                link,
                portal_pin,
            )
        else:
            logger.info('RH portal — e-mail para %s | link=%s', destino, link)
        return True
    except Exception as exc:
        logger.exception('RH: erro ao enviar e-mail do portal: %s', exc)
        return False


def enviar_email_lembrete_coleta(colaborador, documentos_pendentes: list[str]) -> bool:
    """E-mail de lembrete ao candidato com lista de documentos pendentes."""
    token = colaborador.token_portal
    if not token or not colaborador.email:
        return False
    return enviar_link_portal_email(
        colaborador.email,
        colaborador.nome,
        token,
        lembrete=True,
        documentos_pendentes=documentos_pendentes,
    )


def enviar_email_solicitacao_pendencias(
    colaborador,
    pendencias: list[dict],
    *,
    portal_pin: str | None = None,
) -> bool:
    """E-mail ao colaborador com dados e documentos faltando na coleta."""
    token = colaborador.token_portal
    if not token or not colaborador.email:
        return False
    return enviar_link_portal_email(
        colaborador.email,
        colaborador.nome,
        token,
        solicitacao_pendencias=True,
        pendencias_coleta=pendencias,
        portal_pin=portal_pin,
    )


def enviar_email_reenvio_documento(
    colaborador,
    documento,
    dias_restantes: int,
    *,
    portal_pin: str | None = None,
) -> bool:
    """E-mail ao colaborador pedindo reenvio de documento vencido/vencendo."""
    token = colaborador.token_portal
    if not token or not colaborador.email:
        return False
    if dias_restantes < 0:
        motivo_texto = 'está vencido'
    elif dias_restantes == 0:
        motivo_texto = 'vence hoje'
    else:
        motivo_texto = f'vence em {dias_restantes} dia(s)'
    return enviar_link_portal_email(
        colaborador.email,
        colaborador.nome,
        token,
        reenvio=True,
        documento_nome=documento.tipo.nome,
        motivo_texto=motivo_texto,
        portal_pin=portal_pin,
    )


def enviar_link_portal_candidato(
    colaborador,
    pendencias_iniciais: list[dict] | None = None,
    *,
    portal_pin: str | None = None,
) -> dict:
    """Envia o link do portal ao candidato por e-mail e WhatsApp."""
    if not envio_portal_candidato_ativo():
        logger.debug('RH: envio do portal ao candidato desativado (RH_ENVIO_PORTAL_CANDIDATO_ATIVO)')
        return {'email': False, 'whatsapp': False}
    from recursos_humanos.services.documentos import analisar_pendencias_coleta

    token = colaborador.token_portal
    if not token:
        return {'email': False, 'whatsapp': False}
    pendencias = pendencias_iniciais if pendencias_iniciais is not None else analisar_pendencias_coleta(colaborador)
    email_ok = False
    if colaborador.email:
        email_ok = enviar_link_portal_email(
            colaborador.email,
            colaborador.nome,
            token,
            primeiro_acesso=bool(pendencias),
            pendencias_coleta=pendencias,
            portal_pin=portal_pin,
        )
    whatsapp_ok = enviar_whatsapp_portal_colaborador(
        colaborador,
        modo='inicial',
        pendencias_coleta=pendencias,
        portal_pin=portal_pin,
    )
    return {'email': email_ok, 'whatsapp': whatsapp_ok}


def enviar_whatsapp_portal_colaborador(
    colaborador,
    *,
    modo: str = 'inicial',
    pendencias_coleta: list[dict] | None = None,
    documentos_pendentes: list[str] | None = None,
    documento_nome: str = '',
    motivo_texto: str = '',
    base_url: str | None = None,
    portal_pin: str | None = None,
) -> bool:
    if not envio_portal_candidato_ativo():
        logger.debug('RH: envio WhatsApp do portal desativado (RH_ENVIO_PORTAL_CANDIDATO_ATIVO)')
        return False
    telefone = (colaborador.telefone or '').strip()
    token = colaborador.token_portal
    if not telefone or not token:
        return False
    if not _whatsapp_configurado():
        logger.debug('RH: WhatsApp não configurado — notificação do portal não enviada')
        return False
    link = _montar_link_portal(token, base_url)
    msg = _montar_texto_whatsapp_portal(
        colaborador.nome,
        link,
        modo=modo,
        documento_nome=documento_nome,
        motivo_texto=motivo_texto,
        pendencias_coleta=pendencias_coleta,
        documentos_pendentes=documentos_pendentes,
        portal_pin=portal_pin,
    )
    return _enviar_whatsapp_se_configurado(telefone, msg)


def enviar_link_portal_whatsapp(
    telefone: str,
    colaborador_nome: str,
    token: str,
    base_url: str | None = None,
    *,
    pendencias_coleta: list[dict] | None = None,
    portal_pin: str | None = None,
) -> bool:
    """Compatibilidade: envio simples de link do portal por WhatsApp."""
    if not envio_portal_candidato_ativo():
        return False
    if not telefone or not token:
        return False
    if not _whatsapp_configurado():
        logger.debug('RH: WhatsApp não configurado — link do portal não enviado por WhatsApp')
        return False
    link = _montar_link_portal(token, base_url)
    msg = _montar_texto_whatsapp_portal(
        colaborador_nome,
        link,
        modo='inicial',
        pendencias_coleta=pendencias_coleta,
        portal_pin=portal_pin,
    )
    return _enviar_whatsapp_se_configurado(telefone, msg)

