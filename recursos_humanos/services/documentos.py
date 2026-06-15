"""Ações e regras sobre documentos do colaborador."""
from __future__ import annotations

from django.utils import timezone

from recursos_humanos.models import Colaborador, DocumentoColaborador
from recursos_humanos.services.admissao_actions import _autor, registrar_historico
from recursos_humanos.services.alertas_config import obter_configuracao_alertas


def _janela_reenvio_dias() -> int:
    return obter_configuracao_alertas().dias_antecedencia_documentos


def documento_dias_restantes(doc: DocumentoColaborador) -> int | None:
    if not doc.tipo.tem_validade or not doc.vencimento:
        return None
    return (doc.vencimento - timezone.localdate()).days


def documento_esta_vencido(doc: DocumentoColaborador) -> bool:
    dias = documento_dias_restantes(doc)
    return dias is not None and dias < 0


def documento_esta_vencendo(doc: DocumentoColaborador) -> bool:
    dias = documento_dias_restantes(doc)
    if dias is None:
        return False
    return 0 <= dias <= _janela_reenvio_dias()


def documento_alerta_vencimento(doc: DocumentoColaborador) -> bool:
    dias = documento_dias_restantes(doc)
    if dias is None:
        return False
    return dias <= _janela_reenvio_dias()


def documento_conta_como_recebido(doc: DocumentoColaborador) -> bool:
    if doc.status != DocumentoColaborador.Status.RECEBIDO:
        return False
    if doc.reenvio_solicitado:
        return False
    if documento_esta_vencido(doc):
        return False
    return True


def documento_precisa_atencao_coleta(doc: DocumentoColaborador) -> bool:
    """Pendência na coleta: faltando, vencido ou aguardando reenvio."""
    if doc.reenvio_solicitado:
        return True
    if doc.status == DocumentoColaborador.Status.FALTANDO:
        if doc.tipo.obrigatorio:
            return True
        if (doc.observacao or '').strip():
            return True
        return False
    if doc.status == DocumentoColaborador.Status.RECEBIDO and documento_esta_vencido(doc):
        return True
    return False


def documentos_pendentes_candidato(colaborador: Colaborador) -> list[str]:
    """Documentos que o candidato ainda precisa enviar ou reenviar no portal."""
    pendentes: list[str] = []
    for doc in colaborador.documentos.select_related('tipo').order_by('tipo__ordem', 'tipo__nome'):
        if doc.reenvio_solicitado:
            pendentes.append(doc.tipo.nome)
        elif doc.status == DocumentoColaborador.Status.FALTANDO:
            if doc.tipo.obrigatorio or (doc.observacao or '').strip():
                pendentes.append(doc.tipo.nome)
        elif doc.status == DocumentoColaborador.Status.PENDENTE and not doc.arquivo:
            pendentes.append(doc.tipo.nome)
    return pendentes


def documento_precisa_atencao(doc: DocumentoColaborador, colaborador: Colaborador | None = None) -> bool:
    if doc.status == DocumentoColaborador.Status.PENDENTE:
        return True
    return documento_precisa_atencao_coleta(doc)


def colaborador_tem_pendencia_documentos(colaborador: Colaborador) -> bool:
    docs = colaborador.documentos.select_related('tipo')
    return any(documento_precisa_atencao(doc, colaborador) for doc in docs)


def colaborador_pendencia_aprovacao_docs(colaborador: Colaborador) -> bool:
    return colaborador.documentos.filter(
        status=DocumentoColaborador.Status.PENDENTE,
    ).exists()


def etapa_fluxo_efetiva(colaborador: Colaborador) -> int:
    """
    Etapa operacional do fluxo. Qualquer pendência de documento
    (faltando, vencido, reenvio ou aguardando aprovação na coleta) reabre a etapa 2.
    """
    if colaborador_tem_pendencia_documentos(colaborador):
        return 2
    return colaborador.etapa_admissao


def admissao_etapa_concluida(colaborador: Colaborador, num: int) -> bool:
    """Indica se a etapa N está de fato concluída (considera pendências de documentos)."""
    etapa_reg = colaborador.etapa_admissao
    if num > etapa_reg:
        return False
    if num == 5:
        from recursos_humanos.services.admissao_actions import colaborador_admissao_concluida

        return colaborador_admissao_concluida(colaborador)
    if colaborador_tem_pendencia_documentos(colaborador) and num in (2, 3):
        return False
    return num < etapa_reg


def colaborador_documentos_recebidos_validos(colaborador: Colaborador) -> int:
    docs = colaborador.documentos.select_related('tipo')
    return sum(1 for doc in docs if documento_conta_como_recebido(doc))


def documento_elegivel_reenvio(doc: DocumentoColaborador) -> tuple[bool, int | None]:
    """True se o documento pode ter reenvio solicitado (vencido ou na janela de alerta)."""
    if doc.reenvio_solicitado:
        return False, documento_dias_restantes(doc)
    if not doc.tipo.tem_validade or not doc.vencimento:
        return False, None
    if doc.status != DocumentoColaborador.Status.RECEBIDO:
        return False, None
    dias = documento_dias_restantes(doc)
    if dias is None or dias > _janela_reenvio_dias():
        return False, dias
    return True, dias


def _reabrir_pendencia_documentos(colaborador: Colaborador, descricao: str, autor: str) -> None:
    registrar_historico(
        colaborador,
        colaborador.etapa_admissao or 0,
        descricao,
        autor,
        concluido=False,
    )


def solicitar_reenvio_documento(documento: DocumentoColaborador, user) -> tuple[bool, str]:
    """
    Solicita reenvio mantendo o arquivo atual. O colaborador poderá enviar outro
    pelo portal, que substituirá o anterior após aprovação do RH.
    """
    elegivel, dias = documento_elegivel_reenvio(documento)
    if not elegivel:
        return False, 'Este documento não está elegível para solicitação de reenvio.'

    colaborador = documento.colaborador
    if colaborador.status not in (
        colaborador.Status.EM_ADMISSAO,
        colaborador.Status.ATIVO,
    ):
        return False, 'Reenvio só para colaboradores em admissão ou ativos.'

    if not (colaborador.email or '').strip():
        return False, 'Colaborador sem e-mail cadastrado.'

    documento.reenvio_solicitado = True
    documento.save(update_fields=['reenvio_solicitado', 'atualizado_em'])

    autor = _autor(user)
    _reabrir_pendencia_documentos(
        colaborador,
        f'Reenvio de {documento.tipo.nome} solicitado por {autor}',
        autor,
    )

    if not colaborador.token_portal_valido():
        colaborador.gerar_token_portal(dias=30)

    from recursos_humanos.services.notificacoes import enviar_email_reenvio_documento

    email_ok = enviar_email_reenvio_documento(colaborador, documento, dias or 0)
    if email_ok:
        return True, f'Reenvio de "{documento.tipo.nome}" solicitado. E-mail enviado ao colaborador.'
    return True, (
        f'Reenvio de "{documento.tipo.nome}" registrado, '
        f'mas não foi possível enviar o e-mail. Verifique o endereço cadastrado.'
    )
