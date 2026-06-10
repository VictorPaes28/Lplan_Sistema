"""Ações de escrita no fluxo de admissão e documentos."""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from recursos_humanos.models import (
    AdmissaoHistorico,
    Colaborador,
    DocumentoColaborador,
    ObraLocal,
    TipoDocumento,
)


def _autor(user) -> str:
    if not user or not user.is_authenticated:
        return 'Sistema'
    return user.get_full_name() or user.username


def registrar_historico(colaborador, etapa: int, descricao: str, autor: str, *, concluido: bool = True):
    return AdmissaoHistorico.objects.create(
        colaborador=colaborador,
        etapa=etapa,
        descricao=descricao,
        autor=autor,
        concluido=concluido,
    )


def instanciar_documentos(colaborador: Colaborador):
    existentes = set(colaborador.documentos.values_list('tipo_id', flat=True))
    novos = []
    for tipo in TipoDocumento.objects.all():
        if tipo.pk in existentes:
            continue
        novos.append(
            DocumentoColaborador(
                colaborador=colaborador,
                tipo=tipo,
                status=DocumentoColaborador.Status.FALTANDO,
            )
        )
    if novos:
        DocumentoColaborador.objects.bulk_create(novos)


@transaction.atomic
def criar_requisicao(cleaned_data, user) -> Colaborador:
    obra: ObraLocal = cleaned_data['obra']
    colab = Colaborador.objects.create(
        nome=cleaned_data['nome'].strip(),
        cpf=cleaned_data['cpf'].strip(),
        cargo=cleaned_data['cargo'].strip(),
        status=Colaborador.Status.EM_ADMISSAO,
        etapa_admissao=2,
        data_admissao=cleaned_data['data_inicio'],
        tipo_contrato=cleaned_data['tipo_contrato'],
        salario=cleaned_data['salario'],
        gestor_aprovador=cleaned_data['gestor'].strip(),
        motivo_admissao=cleaned_data['motivo'],
        observacoes_requisicao=cleaned_data.get('observacoes', ''),
    )
    colab.obras.add(obra)
    instanciar_documentos(colab)
    autor = _autor(user)
    registrar_historico(colab, 1, 'Requisição criada', f'RH — {autor}')
    registrar_historico(colab, 1, f'Candidato aprovado pelo gestor {colab.gestor_aprovador}', colab.gestor_aprovador)
    registrar_historico(colab, 2, 'Link de coleta enviado ao candidato', 'Sistema automático')
    return colab


def _calcular_vencimento(tipo: TipoDocumento):
    if tipo.tem_validade and tipo.dias_validade:
        return timezone.localdate() + timedelta(days=tipo.dias_validade)
    return None


@transaction.atomic
def atualizar_status_documento(doc: DocumentoColaborador, status: str, observacao: str, user):
    doc.status = status
    doc.observacao = (observacao or '').strip()
    if status == DocumentoColaborador.Status.RECEBIDO:
        doc.vencimento = _calcular_vencimento(doc.tipo)
    elif status == DocumentoColaborador.Status.FALTANDO:
        doc.vencimento = None
    doc.save(update_fields=['status', 'observacao', 'vencimento', 'atualizado_em'])
    registrar_historico(
        doc.colaborador,
        doc.colaborador.etapa_admissao,
        f'Documento «{doc.tipo.nome}» marcado como {doc.get_status_display()}',
        _autor(user),
    )


@transaction.atomic
def upload_documento_arquivo(doc: DocumentoColaborador, arquivo, user):
    if doc.arquivo:
        doc.arquivo.delete(save=False)
    doc.arquivo = arquivo
    doc.status = DocumentoColaborador.Status.RECEBIDO
    doc.vencimento = _calcular_vencimento(doc.tipo)
    doc.save(update_fields=['arquivo', 'status', 'vencimento', 'atualizado_em'])
    registrar_historico(
        doc.colaborador,
        doc.colaborador.etapa_admissao,
        f'Arquivo recebido: {doc.tipo.nome}',
        _autor(user),
    )


def _docs_obrigatorios_ok(colaborador: Colaborador) -> bool:
    return colaborador.documentos_obrigatorios_pendentes() == 0


@transaction.atomic
def avancar_etapa_admissao(colaborador: Colaborador, user) -> tuple[bool, str]:
    etapa = colaborador.etapa_admissao
    autor = _autor(user)

    if etapa == 1:
        colaborador.etapa_admissao = 2
        colaborador.save(update_fields=['etapa_admissao', 'atualizado_em'])
        registrar_historico(colaborador, 2, 'Coleta de documentos iniciada', autor)
        return True, 'Etapa avançada para Coleta de Docs.'

    if etapa == 2:
        if not _docs_obrigatorios_ok(colaborador):
            return False, 'Ainda há documentos obrigatórios pendentes.'
        colaborador.etapa_admissao = 3
        colaborador.save(update_fields=['etapa_admissao', 'atualizado_em'])
        registrar_historico(colaborador, 3, 'Documentação encaminhada para aprovação do RH', autor)
        return True, 'Encaminhado para Aprovação RH.'

    if etapa == 3:
        return False, 'Use «Aprovar documentação» nesta etapa.'

    if etapa == 4:
        colaborador.etapa_admissao = 5
        colaborador.status = Colaborador.Status.ATIVO
        colaborador.save(update_fields=['etapa_admissao', 'status', 'atualizado_em'])
        registrar_historico(colaborador, 5, 'Admissão concluída — colaborador ativo', autor)
        return True, 'Colaborador ativado com sucesso.'

    return False, 'Não há próxima etapa.'


@transaction.atomic
def aprovar_documentacao(colaborador: Colaborador, user) -> tuple[bool, str]:
    if colaborador.etapa_admissao != 3:
        return False, 'Aprovação só na etapa 3.'
    if not _docs_obrigatorios_ok(colaborador):
        return False, 'Documentação incompleta.'
    colaborador.etapa_admissao = 4
    colaborador.save(update_fields=['etapa_admissao', 'atualizado_em'])
    registrar_historico(colaborador, 4, 'Documentação aprovada pelo RH', _autor(user))
    return True, 'Documentação aprovada. Contrato liberado.'


@transaction.atomic
def devolver_admissao(colaborador: Colaborador, motivo: str, user) -> tuple[bool, str]:
    if colaborador.etapa_admissao != 3:
        return False, 'Devolução só na etapa 3.'
    colaborador.etapa_admissao = 2
    colaborador.save(update_fields=['etapa_admissao', 'atualizado_em'])
    registrar_historico(
        colaborador,
        2,
        f'Documentação devolvida: {motivo}',
        _autor(user),
        concluido=False,
    )
    return True, 'Admissão devolvida para coleta de documentos.'


@transaction.atomic
def enviar_contrato(colaborador: Colaborador, user) -> tuple[bool, str]:
    if colaborador.etapa_admissao != 4:
        return False, 'Ação disponível na etapa Ass. Contrato.'
    registrar_historico(colaborador, 4, 'Contrato enviado para assinatura', _autor(user))
    return True, 'Contrato marcado como enviado.'


@transaction.atomic
def concluir_admissao(colaborador: Colaborador, user) -> tuple[bool, str]:
    if colaborador.etapa_admissao != 4:
        return False, 'Conclusão só na etapa 4.'
    return avancar_etapa_admissao(colaborador, user)


def sincronizar_obras_gestao():
    """Espelha obras ativas do GestControll em ObraLocal (sem apagar existentes)."""
    from gestao_aprovacao.models import Obra

    criadas = 0
    for obra in Obra.objects.filter(ativo=True).only('id', 'nome'):
        nome = (obra.nome or '').strip()
        if not nome:
            continue
        local, created = ObraLocal.objects.get_or_create(
            nome=nome,
            defaults={'gestao_obra_id': obra.pk},
        )
        if not created and local.gestao_obra_id is None:
            local.gestao_obra_id = obra.pk
            local.save(update_fields=['gestao_obra_id'])
        if created:
            criadas += 1
    return criadas
