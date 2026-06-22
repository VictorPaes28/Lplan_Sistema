"""E-mails automáticos de vencimento de contrato (todos os tipos de PrazoContrato)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from recursos_humanos.models import Colaborador, NotificacaoEnviada, PrazoContrato
from recursos_humanos.services.alertas_config import obter_configuracao_alertas

logger = logging.getLogger(__name__)

DIAS_ANTECEDENCIA_EXPERIENCIA = 3
DIAS_ANTECEDENCIA_FIM = 15
DIAS_ANTECEDENCIA_ESTAGIO_2ANOS = 30
LIMITE_ESTAGIO_DIAS = 730


@dataclass(frozen=True)
class AlertaContrato:
    tipo_alerta: str
    data_referencia: date
    titulo_email: str
    subtitulo_email: str
    texto_decisao: str
    marco: int | None = None


def _obras_colaborador(colaborador: Colaborador) -> str:
    nomes = list(colaborador.obras.order_by('nome').values_list('nome', flat=True))
    return ', '.join(nomes) if nomes else 'Não informada'


def _destinatarios_rh() -> list[str]:
    config = obter_configuracao_alertas()
    if not config.notificar_email:
        return []
    emails: list[str] = []
    vistos: set[str] = set()
    for user in config.responsaveis.filter(is_active=True):
        email = (user.email or '').strip()
        if email and email.lower() not in vistos:
            vistos.add(email.lower())
            emails.append(email)
    return emails


def _url_colaborador(colaborador_id: int, prazo_id: int | None = None) -> str:
    from urllib.parse import urlencode

    base = getattr(settings, 'SITE_URL', '').rstrip('/')
    path = reverse('recursos_humanos:colaboradores_list')
    params = {'abrir_colaborador': colaborador_id}
    if prazo_id:
        params['abrir_prazo_decisao'] = prazo_id
    return f'{base}{path}?{urlencode(params)}'


def _tipo_contrato_label(colaborador: Colaborador, prazo: PrazoContrato) -> str:
    if (colaborador.tipo_contrato or '').strip() == 'Temporário':
        return 'Temporário'
    return prazo.get_tipo_display()


def _dias_ate(data: date, hoje: date) -> int:
    return (data - hoje).days


def _alertas_experiencia(prazo: PrazoContrato, hoje: date) -> list[AlertaContrato]:
    from recursos_humanos.services.prazo_contrato import (
        MARCO_EXPERIENCIA_1,
        MARCO_EXPERIENCIA_2,
        obter_data_admissao_oficial,
    )

    colaborador = prazo.colaborador
    data_base = obter_data_admissao_oficial(colaborador)
    if not data_base:
        return []
    alertas = []
    for dias_marco, tipo in (
        (MARCO_EXPERIENCIA_1, NotificacaoEnviada.TipoAlerta.EXPERIENCIA_45),
        (MARCO_EXPERIENCIA_2, NotificacaoEnviada.TipoAlerta.EXPERIENCIA_90),
    ):
        data_marco = data_base + timedelta(days=dias_marco)
        if prazo.data_fim and data_marco > prazo.data_fim and prazo.renovacao_numero == 0:
            continue
        if _dias_ate(data_marco, hoje) != DIAS_ANTECEDENCIA_EXPERIENCIA:
            continue
        if dias_marco == MARCO_EXPERIENCIA_1:
            texto = (
                'Faltam 3 dias para o fim do primeiro período de experiência. '
                'Decidir: prorrogar (até 90 dias), efetivar antecipadamente ou dispensar.'
            )
        else:
            texto = (
                'Faltam 3 dias para o fim do período total de experiência. '
                'Decidir: efetivar em CLT indeterminado ou dispensar ao término.'
            )
        alertas.append(AlertaContrato(
            tipo_alerta=tipo,
            marco=dias_marco,
            data_referencia=data_marco,
            titulo_email='Vencimento de período de experiência',
            subtitulo_email=f'Marco de {dias_marco} dias — vence em {data_marco:%d/%m/%Y}',
            texto_decisao=texto,
        ))
    return alertas


def _alerta_fim_prazo(
    prazo: PrazoContrato,
    hoje: date,
    *,
    tipo_alerta: str,
    titulo: str,
    texto: str,
) -> AlertaContrato | None:
    if not prazo.data_fim:
        return None
    if _dias_ate(prazo.data_fim, hoje) != DIAS_ANTECEDENCIA_FIM:
        return None
    return AlertaContrato(
        tipo_alerta=tipo_alerta,
        data_referencia=prazo.data_fim,
        titulo_email=titulo,
        subtitulo_email=f'Vencimento em {prazo.data_fim:%d/%m/%Y} (15 dias de antecedência)',
        texto_decisao=texto,
    )


def _alertas_por_prazo(prazo: PrazoContrato, hoje: date) -> list[AlertaContrato]:
    colab = prazo.colaborador
    tipo_colab = (colab.tipo_contrato or '').strip()

    if prazo.tipo == PrazoContrato.Tipo.EXPERIENCIA:
        return _alertas_experiencia(prazo, hoje)

    if tipo_colab == 'Temporário':
        alerta = _alerta_fim_prazo(
            prazo,
            hoje,
            tipo_alerta=NotificacaoEnviada.TipoAlerta.TEMPORARIO_FIM,
            titulo='Vencimento de contrato temporário',
            texto=(
                'Faltam 15 dias para o fim do contrato temporário. '
                'Prazo máximo legal: 270 dias (180 + prorrogação de 90). '
                'Avaliar renovação dentro do limite ou encerramento.'
            ),
        )
        return [alerta] if alerta else []

    if prazo.tipo == PrazoContrato.Tipo.DETERMINADO:
        alerta = _alerta_fim_prazo(
            prazo,
            hoje,
            tipo_alerta=NotificacaoEnviada.TipoAlerta.DETERMINADO_FIM,
            titulo='Vencimento de contrato por prazo determinado',
            texto=(
                'Faltam 15 dias para o fim do contrato. Se não houver renovação formal '
                'ou rescisão, o vínculo pode ser considerado CLT por prazo indeterminado '
                'após 2 anos de vigência.'
            ),
        )
        return [alerta] if alerta else []

    if prazo.tipo == PrazoContrato.Tipo.ESTAGIO:
        alertas = []
        alerta_fim = _alerta_fim_prazo(
            prazo,
            hoje,
            tipo_alerta=NotificacaoEnviada.TipoAlerta.ESTAGIO_FIM,
            titulo='Vencimento de período de estágio',
            texto=(
                'Faltam 15 dias para o fim deste período de estágio. '
                'Avaliar renovação, efetivação ou encerramento dentro do limite legal de 2 anos.'
            ),
        )
        if alerta_fim:
            alertas.append(alerta_fim)

        data_limite_2anos = prazo.data_inicio + timedelta(days=LIMITE_ESTAGIO_DIAS)
        if _dias_ate(data_limite_2anos, hoje) == DIAS_ANTECEDENCIA_ESTAGIO_2ANOS:
            alertas.append(AlertaContrato(
                tipo_alerta=NotificacaoEnviada.TipoAlerta.ESTAGIO_2ANOS,
                data_referencia=data_limite_2anos,
                titulo_email='Estágio — limite de 2 anos',
                subtitulo_email=f'Completa 2 anos em {data_limite_2anos:%d/%m/%Y}',
                texto_decisao=(
                    'Faltam 30 dias para completar 2 anos de estágio na mesma empresa. '
                    'Ultrapassar esse prazo pode caracterizar vínculo empregatício com '
                    'direitos CLT retroativos (Lei 11.788/2008).'
                ),
            ))
        return alertas

    if prazo.tipo == PrazoContrato.Tipo.PJ:
        alerta = _alerta_fim_prazo(
            prazo,
            hoje,
            tipo_alerta=NotificacaoEnviada.TipoAlerta.PJ_FIM,
            titulo='Vencimento de contrato PJ',
            texto=(
                'Faltam 15 dias para o fim do contrato PJ. Rescisão antecipada sem '
                'justa causa pode gerar indenização dos dias restantes (art. 603 CC).'
            ),
        )
        return [alerta] if alerta else []

    return []


def _montar_contexto(prazo: PrazoContrato, alerta: AlertaContrato) -> dict:
    colab = prazo.colaborador
    return {
        'nome_colaborador': colab.nome,
        'cargo': colab.cargo or '—',
        'tipo_contrato': _tipo_contrato_label(colab, prazo),
        'obras': _obras_colaborador(colab),
        'data_inicio': prazo.data_inicio.strftime('%d/%m/%Y'),
        'data_vencimento': alerta.data_referencia.strftime('%d/%m/%Y'),
        'titulo_email': alerta.titulo_email,
        'subtitulo_email': alerta.subtitulo_email,
        'texto_decisao': alerta.texto_decisao,
        'url_colaborador': _url_colaborador(colab.pk, prazo.pk),
    }


def _montar_texto_plano(ctx: dict) -> str:
    return '\n'.join([
        f'[LPLAN RH] {ctx["titulo_email"]}',
        '',
        f'Colaborador: {ctx["nome_colaborador"]}',
        f'Tipo de contrato: {ctx["tipo_contrato"]}',
        f'Cargo: {ctx["cargo"]}',
        f'Obra(s): {ctx["obras"]}',
        f'Início: {ctx["data_inicio"]}',
        f'Data de vencimento: {ctx["data_vencimento"]}',
        '',
        ctx['texto_decisao'],
        '',
        f'Abrir no sistema: {ctx["url_colaborador"]}',
        '',
        'Mensagem automática — não responda a este e-mail.',
    ])


def enviar_email_alerta_contrato(prazo: PrazoContrato, alerta: AlertaContrato) -> bool:
    destinatarios = _destinatarios_rh()
    if not destinatarios:
        logger.warning(
            'RH contrato: sem destinatários RH para %s (%s)',
            prazo.colaborador.nome,
            alerta.tipo_alerta,
        )
        return False

    ctx = _montar_contexto(prazo, alerta)
    assunto = (
        f'[LPLAN RH] {alerta.titulo_email} — '
        f'{ctx["nome_colaborador"]} — {ctx["data_vencimento"]}'
    )
    remetente = getattr(settings, 'DEFAULT_FROM_EMAIL', 'sistema@lplan.com.br')

    try:
        msg = EmailMultiAlternatives(assunto, _montar_texto_plano(ctx), remetente, destinatarios)
        msg.attach_alternative(
            render_to_string('recursos_humanos/emails/vencimento_contrato.html', ctx),
            'text/html',
        )
        msg.send()
        return True
    except Exception:
        logger.exception(
            'RH contrato: falha ao enviar e-mail para %s (%s)',
            prazo.colaborador.nome,
            alerta.tipo_alerta,
        )
        return False


def _ja_notificado(prazo: PrazoContrato, tipo_alerta: str, hoje: date) -> bool:
    return NotificacaoEnviada.objects.filter(
        prazo_contrato=prazo,
        tipo_alerta=tipo_alerta,
        data_envio=hoje,
    ).exists()


def _registrar_envio(prazo: PrazoContrato, alerta: AlertaContrato, hoje: date) -> bool:
    try:
        NotificacaoEnviada.objects.create(
            prazo_contrato=prazo,
            tipo_alerta=alerta.tipo_alerta,
            marco=alerta.marco,
            data_envio=hoje,
        )
        return True
    except IntegrityError:
        return False


def processar_notificacoes_contrato(*, hoje=None, dry_run: bool = False) -> dict:
    hoje = hoje or timezone.localdate()
    stats = {
        'prazos_analisados': 0,
        'notificacoes_enviadas': 0,
        'notificacoes_ignoradas': 0,
        'falhas': 0,
    }

    prazos = (
        PrazoContrato.objects.filter(
            status=PrazoContrato.Status.ATIVO,
            colaborador__status__in=(
                Colaborador.Status.ATIVO,
                Colaborador.Status.EM_ADMISSAO,
            ),
        )
        .select_related('colaborador')
        .prefetch_related('colaborador__obras')
    )

    for prazo in prazos:
        stats['prazos_analisados'] += 1
        for alerta in _alertas_por_prazo(prazo, hoje):
            if _ja_notificado(prazo, alerta.tipo_alerta, hoje):
                stats['notificacoes_ignoradas'] += 1
                continue

            if dry_run:
                stats['notificacoes_enviadas'] += 1
                continue

            if not enviar_email_alerta_contrato(prazo, alerta):
                stats['falhas'] += 1
                continue

            if _registrar_envio(prazo, alerta, hoje):
                stats['notificacoes_enviadas'] += 1
            else:
                stats['notificacoes_ignoradas'] += 1

    return stats
