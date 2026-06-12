"""Notificações RH no sino central (core.Notification)."""
from __future__ import annotations

import logging

from django.contrib.auth.models import User
from django.urls import reverse

from core.notification_utils import criar_notificacao, marcar_lidas_por_event_key
from recursos_humanos.models import Colaborador, DocumentoColaborador
from recursos_humanos.services.alertas_config import obter_configuracao_alertas, usuarios_elegiveis_alertas

logger = logging.getLogger(__name__)


def _url_gestor_aprovar(colaborador_id: int) -> str:
    return reverse('recursos_humanos:gestor_aprovar_requisicao', args=[colaborador_id])


def _url_admissao(colaborador_id: int) -> str:
    return f"{reverse('recursos_humanos:admissao')}?id={colaborador_id}"


def _url_colaborador(colaborador_id: int) -> str:
    return reverse('recursos_humanos:colaborador_detalhe', args=[colaborador_id])


def _event_colab(colaborador_id: int, sufixo: str = '') -> str:
    base = f'rh:colab:{colaborador_id}'
    return f'{base}:{sufixo}' if sufixo else base


def _canal_sistema_ativo() -> bool:
    return obter_configuracao_alertas().canal_notificacao_sistema


def _usuarios_rh() -> list[User]:
    if not _canal_sistema_ativo():
        return []
    config = obter_configuracao_alertas()
    qs = config.responsaveis.filter(is_active=True)
    if qs.exists():
        return list(qs)
    return list(usuarios_elegiveis_alertas())


def _notificar_usuarios(
    usuarios,
    tipo: str,
    titulo: str,
    mensagem: str,
    *,
    url: str = '',
    event_key: str = '',
) -> None:
    if not usuarios:
        return
    try:
        criar_notificacao(usuarios, tipo, titulo, mensagem, url=url, event_key=event_key)
    except Exception as exc:
        logger.warning('RH: falha ao criar notificação no sino (%s): %s', tipo, exc)


def _notificar_rh(tipo: str, titulo: str, mensagem: str, *, url: str = '', event_key: str = '') -> None:
    _notificar_usuarios(_usuarios_rh(), tipo, titulo, mensagem, url=url, event_key=event_key)


def _destinatarios_reprovacao(colaborador: Colaborador) -> list[User]:
    vistos: set[int] = set()
    dest: list[User] = []
    for user in _usuarios_rh():
        if user.pk not in vistos:
            vistos.add(user.pk)
            dest.append(user)
    criador = colaborador.requisicao_criada_por
    if criador and criador.is_active and criador.pk not in vistos:
        dest.append(criador)
    return dest


def notificar_gestor_requisicao_pendente(colaborador: Colaborador) -> None:
    gestor = colaborador.gestor_aprovador_user
    if not gestor or not gestor.is_active:
        return
    _notificar_usuarios(
        gestor,
        'rh_requisicao_pendente',
        f'Aprovar admissão: {colaborador.nome}',
        f'Cargo {colaborador.cargo}. Requisição aguardando sua aprovação.',
        url=_url_gestor_aprovar(colaborador.pk),
        event_key=_event_colab(colaborador.pk, 'requisicao'),
    )


def notificar_rh_requisicao_reprovada(colaborador: Colaborador) -> None:
    motivo = (colaborador.requisicao_motivo_reprovacao or '').strip()
    msg = f'Gestor {colaborador.gestor_aprovador} reprovou a requisição de {colaborador.nome}.'
    if motivo:
        msg += f' Motivo: {motivo}'
    _notificar_usuarios(
        _destinatarios_reprovacao(colaborador),
        'rh_requisicao_reprovada',
        f'Requisição reprovada — {colaborador.nome}',
        msg,
        url=_url_admissao(colaborador.pk),
        event_key=_event_colab(colaborador.pk, 'reprovada'),
    )


def notificar_rh_coleta_iniciada(colaborador: Colaborador) -> None:
    marcar_lidas_por_event_key(
        _event_colab(colaborador.pk, 'requisicao'),
        notification_types=('rh_requisicao_pendente',),
    )
    _notificar_rh(
        'rh_coleta_docs',
        f'Coleta de docs: {colaborador.nome}',
        f'Gestor aprovou a requisição. Candidato em etapa de envio de documentos ({colaborador.cargo}).',
        url=_url_admissao(colaborador.pk),
        event_key=_event_colab(colaborador.pk, 'coleta'),
    )


def notificar_rh_documento_recebido(doc: DocumentoColaborador) -> None:
    colab = doc.colaborador
    _notificar_rh(
        'rh_documento_recebido',
        f'Documento recebido — {colab.nome}',
        f'«{doc.tipo.nome}» enviado pelo candidato no portal.',
        url=_url_admissao(colab.pk),
        event_key=_event_colab(colab.pk, f'doc:{doc.pk}'),
    )


def notificar_rh_documentacao_pronta(colaborador: Colaborador) -> None:
    _notificar_rh(
        'rh_documentacao_pronta',
        f'Documentação completa — {colaborador.nome}',
        'Todos os documentos obrigatórios foram recebidos. Pronto para aprovação do RH.',
        url=_url_admissao(colaborador.pk),
        event_key=_event_colab(colaborador.pk, 'docs_ok'),
    )


def notificar_rh_aprovacao_pendente(colaborador: Colaborador) -> None:
    _notificar_rh(
        'rh_admissao_pendente',
        f'Aprovar admissão — {colaborador.nome}',
        'Documentação na etapa de aprovação do RH.',
        url=_url_admissao(colaborador.pk),
        event_key=_event_colab(colaborador.pk, 'aprovacao_rh'),
    )


def sincronizar_alertas_sino() -> int:
    """Cria notificações no sino para alertas críticos ainda não notificados."""
    if not _canal_sistema_ativo():
        return 0
    from core.models import Notification
    from recursos_humanos.services.alerts import gerar_alertas

    usuarios = _usuarios_rh()
    if not usuarios:
        return 0

    criadas = 0
    for alerta in gerar_alertas():
        if alerta.urgencia not in ('red', 'yellow'):
            continue

        if alerta.tipo == 'Documento vencido':
            tipo = 'rh_documento_vencendo'
            titulo = f'Documento vencido — {alerta.colaborador_nome}'
        elif alerta.tipo == 'Documento vencendo':
            tipo = 'rh_documento_vencendo'
            titulo = f'Documento vencendo — {alerta.colaborador_nome}'
        elif alerta.tipo == 'Admissão em andamento':
            if alerta.acao != 'Aprovar':
                continue
            tipo = 'rh_admissao_pendente'
            titulo = f'Admissão pendente — {alerta.colaborador_nome}'
        else:
            continue

        event_key = f'rh:alerta:{alerta.id}'
        novos = []
        for user in usuarios:
            if Notification.objects.filter(
                user=user, event_key=event_key, is_read=False,
            ).exists():
                continue
            novos.append(user)

        if not novos:
            continue

        _notificar_usuarios(
            novos,
            tipo,
            titulo,
            alerta.detalhe,
            url=alerta.url,
            event_key=event_key,
        )
        criadas += len(novos)

    return criadas
