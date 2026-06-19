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
    return documento_status_fluxo_ok(doc)


def documento_status_fluxo_ok(doc: DocumentoColaborador) -> bool:
    """Critério unificado UI + backend (equivalente ao status visual «ok»)."""
    if doc.reenvio_solicitado:
        return False
    if doc.status == DocumentoColaborador.Status.PENDENTE:
        return False
    if doc.status == DocumentoColaborador.Status.FALTANDO:
        return False
    if doc.status == DocumentoColaborador.Status.RECEBIDO:
        return not documento_esta_vencido(doc)
    return False


def resumo_documentacao_fluxo(colaborador: Colaborador) -> dict:
    docs = list(
        colaborador.documentos.select_related('tipo').order_by('tipo__ordem', 'tipo__nome'),
    )
    total = len(docs)
    recebidos = sum(1 for doc in docs if documento_status_fluxo_ok(doc))
    return {
        'total': total,
        'recebidos': recebidos,
        'faltando': total - recebidos,
        'completo': total > 0 and recebidos == total,
    }


def documentacao_fluxo_completa(colaborador: Colaborador) -> bool:
    resumo = resumo_documentacao_fluxo(colaborador)
    if resumo['total'] == 0:
        return True
    return resumo['completo']


def documentacao_obrigatoria_fluxo_ok(colaborador: Colaborador) -> bool:
    docs = colaborador.documentos.select_related('tipo')
    obrigatorios = [doc for doc in docs if doc.tipo.obrigatorio]
    if not obrigatorios:
        return True
    return all(documento_status_fluxo_ok(doc) for doc in obrigatorios)


def conferencia_documentos_operacional(colaborador: Colaborador) -> bool:
    """Conferência de docs ativa: etapa 2 ou pendência documental após etapa 2."""
    if colaborador.status != Colaborador.Status.EM_ADMISSAO:
        return False
    if colaborador.etapa_admissao == 2:
        return True
    if colaborador.etapa_admissao >= 3 and colaborador_tem_pendencia_documentos(colaborador):
        return True
    return False


def portal_permite_envio_documentos(colaborador: Colaborador) -> bool:
    """Candidato pode enviar ou reenviar documentos no portal."""
    if colaborador.status == Colaborador.Status.ATIVO:
        return colaborador_tem_pendencia_documentos(colaborador)
    if colaborador.status != Colaborador.Status.EM_ADMISSAO:
        return False
    if colaborador.etapa_admissao < 2:
        return False
    if colaborador.etapa_admissao >= 3 and not colaborador_tem_pendencia_documentos(colaborador):
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
    return [
        item['label']
        for item in analisar_pendencias_coleta(colaborador)
        if item['tipo'] == 'documento'
    ]


def analisar_pendencias_coleta(colaborador: Colaborador) -> list[dict]:
    """
    Pendências de coleta (dados pessoais + documentos faltando/rejeitados).
    Não inclui documentos vencidos — esses usam «Solicitar reenvio» por item.
    """
    from recursos_humanos.services.admissao_actions import (
        CAMPOS_DADOS_PORTAL_OBRIGATORIOS,
        LABELS_CAMPOS_PORTAL,
        dados_portal_completos,
    )

    itens: list[dict] = []

    if colaborador.status == Colaborador.Status.EM_ADMISSAO and not dados_portal_completos(colaborador):
        for campo in CAMPOS_DADOS_PORTAL_OBRIGATORIOS:
            if not getattr(colaborador, campo, None):
                itens.append({
                    'tipo': 'dado',
                    'label': LABELS_CAMPOS_PORTAL[campo],
                    'detalhe': 'Informação não preenchida no portal',
                })

    for doc in colaborador.documentos.select_related('tipo').order_by('tipo__ordem', 'tipo__nome'):
        if doc.reenvio_solicitado or doc.status == DocumentoColaborador.Status.RECEBIDO:
            continue
        if doc.status == DocumentoColaborador.Status.FALTANDO:
            detalhe = (doc.observacao or '').strip() or 'Documento não enviado'
            itens.append({
                'tipo': 'documento',
                'label': doc.tipo.nome,
                'detalhe': detalhe,
            })
        elif doc.status == DocumentoColaborador.Status.PENDENTE and not doc.arquivo:
            itens.append({
                'tipo': 'documento',
                'label': doc.tipo.nome,
                'detalhe': 'Aguardando envio pelo portal',
            })

    return itens


def colaborador_tem_pendencia_coleta(colaborador: Colaborador) -> bool:
    return bool(analisar_pendencias_coleta(colaborador))


def portal_permite_solicitar_pendencias(colaborador: Colaborador) -> bool:
    """Portal acessível para completar pendências de coleta (não vencimento)."""
    if portal_permite_envio_documentos(colaborador):
        return True
    if colaborador.status != Colaborador.Status.EM_ADMISSAO:
        return False
    if colaborador.etapa_admissao < 2:
        return False
    from recursos_humanos.services.admissao_actions import dados_portal_completos

    return not dados_portal_completos(colaborador)


def colaborador_tem_contato_portal(colaborador: Colaborador) -> bool:
    return bool((colaborador.email or '').strip() or (colaborador.telefone or '').strip())


def pode_solicitar_pendencias_coleta(colaborador: Colaborador, user) -> bool:
    from recursos_humanos.services.papeis_fluxo import usuario_pode_conferir_documentos

    if not user or not getattr(user, 'is_authenticated', False):
        return False
    return (
        bool(analisar_pendencias_coleta(colaborador))
        and colaborador_tem_contato_portal(colaborador)
        and usuario_pode_conferir_documentos(user, colaborador)
        and portal_permite_solicitar_pendencias(colaborador)
    )


def motivo_botao_pendencias_indisponivel(colaborador: Colaborador, user) -> str | None:
    """Explica por que «Solicitar pendências» não aparece (None = botão deve aparecer)."""
    if pode_solicitar_pendencias_coleta(colaborador, user):
        return None
    pendencias = analisar_pendencias_coleta(colaborador)
    if not pendencias:
        return (
            'Não há pendências de coleta detectadas. '
            'Documentos vencidos usam «Solicitar reenvio» em cada linha.'
        )
    if not colaborador_tem_contato_portal(colaborador):
        return 'Cadastre e-mail ou telefone na requisição.'
    from recursos_humanos.services.papeis_fluxo import usuario_pode_conferir_documentos

    if not usuario_pode_conferir_documentos(user, colaborador):
        return 'Sem permissão na Conferência de docs.'
    if not portal_permite_solicitar_pendencias(colaborador):
        return 'O portal não está disponível para este colaborador no momento.'
    return 'Não foi possível habilitar o envio de pendências.'


def portal_modo_envio_restrito(colaborador: Colaborador) -> bool:
    """Portal aceita envio apenas dos itens explicitamente solicitados pelo RH."""
    if colaborador.status == Colaborador.Status.ATIVO:
        return True
    if colaborador.dados_coleta_solicitada:
        return True
    if colaborador.documentos.filter(reenvio_solicitado=True).exists():
        return True
    if colaborador.documentos.filter(coleta_solicitada=True).exists():
        return True
    return False


def _documento_elegivel_coleta_livre(doc: DocumentoColaborador) -> bool:
    if doc.reenvio_solicitado:
        return True
    if doc.status == DocumentoColaborador.Status.FALTANDO:
        return doc.tipo.obrigatorio or bool((doc.observacao or '').strip())
    if doc.status == DocumentoColaborador.Status.PENDENTE and not doc.arquivo:
        return True
    return False


def _portal_coleta_admissao_em_andamento(colaborador: Colaborador) -> bool:
    """Na admissão, documentos ainda pendentes continuam visíveis no portal."""
    return colaborador.status == Colaborador.Status.EM_ADMISSAO


def _documento_liberado_portal_restrito(
    doc: DocumentoColaborador,
    colaborador: Colaborador,
) -> bool:
    if doc.reenvio_solicitado or doc.coleta_solicitada:
        return True
    if _portal_coleta_admissao_em_andamento(colaborador) and _documento_elegivel_coleta_livre(doc):
        return True
    return False


def documento_visivel_no_portal(doc: DocumentoColaborador, colaborador: Colaborador) -> bool:
    if not portal_modo_envio_restrito(colaborador):
        return True
    return _documento_liberado_portal_restrito(doc, colaborador)


def dados_visivel_no_portal(colaborador: Colaborador) -> bool:
    if colaborador.status != Colaborador.Status.EM_ADMISSAO:
        return False
    return True


def documentos_para_exibicao_portal(colaborador: Colaborador) -> list[DocumentoColaborador]:
    docs = list(
        DocumentoColaborador.objects.filter(colaborador_id=colaborador.pk)
        .select_related('tipo')
        .order_by('tipo__ordem', 'tipo__nome')
    )
    if portal_modo_envio_restrito(colaborador):
        docs = [doc for doc in docs if documento_visivel_no_portal(doc, colaborador)]
    return docs


def documento_permite_envio_portal(doc: DocumentoColaborador, colaborador: Colaborador) -> bool:
    if not portal_permite_envio_documentos(colaborador):
        return False
    if doc.arquivo and doc.status == DocumentoColaborador.Status.PENDENTE:
        return False
    if portal_modo_envio_restrito(colaborador):
        return _documento_liberado_portal_restrito(doc, colaborador)
    return _documento_elegivel_coleta_livre(doc)


def portal_permite_editar_dados(colaborador: Colaborador) -> bool:
    from recursos_humanos.services.admissao_actions import dados_portal_completos

    if colaborador.status != Colaborador.Status.EM_ADMISSAO:
        return False
    if colaborador.etapa_admissao < 2:
        return False
    if portal_modo_envio_restrito(colaborador):
        return colaborador.dados_coleta_solicitada
    return not dados_portal_completos(colaborador)


def marcar_pendencias_solicitadas_portal(colaborador: Colaborador, pendencias: list[dict]) -> None:
    """Marca itens solicitados no portal (acumula solicitações anteriores)."""
    labels_docs = {p['label'] for p in pendencias if p.get('tipo') == 'documento'}

    if any(p.get('tipo') == 'dado' for p in pendencias) and not colaborador.dados_coleta_solicitada:
        colaborador.dados_coleta_solicitada = True
        colaborador.save(update_fields=['dados_coleta_solicitada', 'atualizado_em'])

    for doc in colaborador.documentos.select_related('tipo'):
        if doc.tipo.nome in labels_docs and not doc.coleta_solicitada:
            doc.coleta_solicitada = True
            doc.save(update_fields=['coleta_solicitada', 'atualizado_em'])


def documento_precisa_atencao(doc: DocumentoColaborador, colaborador: Colaborador | None = None) -> bool:
    if doc.status == DocumentoColaborador.Status.PENDENTE:
        return True
    return documento_precisa_atencao_coleta(doc)


def coleta_documentos_iniciada(colaborador: Colaborador) -> bool:
    """Coleta no portal após registro da requisição; novas admissões já iniciam na etapa 2."""
    if colaborador.etapa_admissao < 2:
        return False
    if colaborador.status == Colaborador.Status.ATIVO:
        return True
    return True


def colaborador_tem_pendencia_documentos(colaborador: Colaborador) -> bool:
    docs = colaborador.documentos.select_related('tipo')
    return any(documento_precisa_atencao(doc, colaborador) for doc in docs)


def colaborador_pendencia_aprovacao_docs(colaborador: Colaborador) -> bool:
    return colaborador.documentos.filter(
        status=DocumentoColaborador.Status.PENDENTE,
    ).exists()


def etapa_fluxo_efetiva(colaborador: Colaborador) -> int:
    """
    Etapa operacional do fluxo. Pendências de documento reabrem a etapa 2
    somente depois que a coleta foi iniciada (etapa 2 + requisição aprovada).
    """
    if not coleta_documentos_iniciada(colaborador):
        return colaborador.etapa_admissao
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
    if (
        coleta_documentos_iniciada(colaborador)
        and colaborador_tem_pendencia_documentos(colaborador)
        and num in (2, 3)
    ):
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

    from recursos_humanos.services.papeis_fluxo import usuario_pode_conferir_documentos

    if not usuario_pode_conferir_documentos(user, colaborador):
        return False, 'Você não tem permissão para solicitar reenvio nesta etapa.'

    from recursos_humanos.services.notificacoes import envio_portal_candidato_ativo

    if envio_portal_candidato_ativo():
        if not (colaborador.email or '').strip() and not (colaborador.telefone or '').strip():
            return False, 'Colaborador sem e-mail ou telefone cadastrado.'

    documento.reenvio_solicitado = True
    documento.save(update_fields=['reenvio_solicitado', 'atualizado_em'])

    autor = _autor(user)
    _reabrir_pendencia_documentos(
        colaborador,
        f'Reenvio de {documento.tipo.nome} solicitado por {autor}',
        autor,
    )

    from recursos_humanos.services.portal_token import renovar_token_portal_colaborador
    from recursos_humanos.services.notificacoes import (
        enviar_email_reenvio_documento,
        enviar_whatsapp_portal_colaborador,
        envio_portal_candidato_ativo,
    )

    _token, portal_pin = renovar_token_portal_colaborador(colaborador)

    if not envio_portal_candidato_ativo():
        return True, f'Reenvio de "{documento.tipo.nome}" registrado no sistema.'

    email_ok = False
    if (colaborador.email or '').strip():
        email_ok = enviar_email_reenvio_documento(colaborador, documento, dias or 0, portal_pin=portal_pin)
    whatsapp_ok = enviar_whatsapp_portal_colaborador(
        colaborador,
        modo='reenvio',
        documento_nome=documento.tipo.nome,
        motivo_texto=_motivo_reenvio_texto(dias or 0),
        portal_pin=portal_pin,
    )
    if email_ok or whatsapp_ok:
        canais = []
        if email_ok:
            canais.append('e-mail')
        if whatsapp_ok:
            canais.append('WhatsApp')
        return True, f'Reenvio de "{documento.tipo.nome}" solicitado. Enviado por {" e ".join(canais)}.'
    return True, (
        f'Reenvio de "{documento.tipo.nome}" registrado, '
        f'mas não foi possível notificar o colaborador. Verifique e-mail e telefone.'
    )


def _motivo_reenvio_texto(dias: int) -> str:
    if dias < 0:
        return 'está vencido'
    if dias == 0:
        return 'vence hoje'
    return f'vence em {dias} dia(s)'


def portal_tem_acao_disponivel(colaborador: Colaborador) -> bool:
    """Candidato ainda pode editar dados ou enviar documento no portal."""
    if portal_permite_editar_dados(colaborador):
        return True
    if not portal_permite_envio_documentos(colaborador):
        return False
    for doc in documentos_para_exibicao_portal(colaborador):
        if documento_permite_envio_portal(doc, colaborador):
            return True
    return False


def portal_em_modo_confirmacao(colaborador: Colaborador) -> bool:
    """Sem ações pendentes: portal exibe confirmação somente leitura."""
    if colaborador.status not in (
        Colaborador.Status.EM_ADMISSAO,
        Colaborador.Status.ATIVO,
    ):
        return False
    return not portal_tem_acao_disponivel(colaborador)
