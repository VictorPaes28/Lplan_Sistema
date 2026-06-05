"""Separação de anexos recusados (histórico) vs. corrigidos (novo envio / PDF)."""

from __future__ import annotations

from typing import Any

from django.db.models import Max, QuerySet

from gestao_aprovacao.models import Attachment, WorkOrder


def attachments_ativos_queryset(work_order: WorkOrder) -> QuerySet[Attachment]:
    """Anexos válidos para o envio atual e para consolidação em PDF."""
    # Ordenação estável pela sequência de upload para manter o PDF consolidado
    # no mesmo fluxo em que os arquivos entraram no pedido.
    return Attachment.objects.filter(work_order=work_order, recusado=False).order_by('id')


def ordered_attachments_for_consolidation(work_order: WorkOrder) -> list[Attachment]:
    return list(attachments_ativos_queryset(work_order))


def submission_version_for_reject(work_order: WorkOrder) -> int:
    """Versão do pacote que estava em análise no momento da reprovação."""
    max_v = Attachment.objects.filter(
        work_order=work_order,
        recusado=False,
    ).aggregate(m=Max('versao_reaprovacao'))['m']
    return int(max_v or 0)


def mark_submission_attachments_recusados(work_order: WorkOrder) -> int:
    """Marca como recusados os documentos da submissão reprovada (somente consulta)."""
    version = submission_version_for_reject(work_order)
    return Attachment.objects.filter(
        work_order=work_order,
        versao_reaprovacao=version,
        recusado=False,
    ).update(recusado=True)


def assign_new_attachment_version(work_order: WorkOrder) -> int:
    """
    Versão para um novo upload após reprovação.
    Reutiliza a versão da rodada de correção em andamento, se já existir.
    """
    has_recusados = Attachment.objects.filter(work_order=work_order, recusado=True).exists()
    if not has_recusados:
        return 0

    max_ativo = Attachment.objects.filter(
        work_order=work_order,
        recusado=False,
    ).aggregate(m=Max('versao_reaprovacao'))['m']
    if max_ativo is not None:
        return int(max_ativo)

    max_all = Attachment.objects.filter(work_order=work_order).aggregate(
        m=Max('versao_reaprovacao')
    )['m']
    return int(max_all or 0) + 1


def attachment_pode_excluir(attachment: Attachment) -> bool:
    return not attachment.recusado


def build_attachment_display_groups(work_order: WorkOrder) -> dict[str, Any]:
    """Agrupa anexos para exibição na UI (histórico vs. corrigidos)."""
    all_atts = list(
        Attachment.objects.filter(work_order=work_order).order_by('versao_reaprovacao', 'id')
    )
    if not all_atts:
        return {'modo': 'vazio', 'grupos': []}

    recusados = [a for a in all_atts if a.recusado]
    ativos = [a for a in all_atts if not a.recusado]

    if not recusados:
        return {
            'modo': 'normal',
            'grupos': [{
                'key': 'ativos',
                'label': 'Anexos do pedido',
                'hint': '',
                'readonly': False,
                'versao': None,
                'items': ativos,
            }],
        }

    grupos: list[dict[str, Any]] = []
    by_version: dict[int, list[Attachment]] = {}
    for att in recusados:
        by_version.setdefault(att.versao_reaprovacao, []).append(att)

    for versao in sorted(by_version.keys()):
        if versao == 0:
            label = 'Documentos recusados — envio original'
        else:
            label = f'Documentos recusados — reaprovação v{versao}'
        grupos.append({
            'key': 'historico',
            'label': label,
            'hint': 'Somente consulta. Estes arquivos não entram no PDF do novo envio.',
            'readonly': True,
            'versao': versao,
            'items': by_version[versao],
        })

    if ativos:
        versao_ativa = max(a.versao_reaprovacao for a in ativos)
        grupos.append({
            'key': 'corrigidos',
            'label': 'Documentos corrigidos — novo envio',
            'hint': 'Estes arquivos serão usados na geração do PDF para assinatura.',
            'readonly': False,
            'versao': versao_ativa,
            'items': ativos,
        })
    elif work_order.status == 'reprovado':
        grupos.append({
            'key': 'corrigidos_vazio',
            'label': 'Documentos corrigidos — novo envio',
            'hint': 'Adicione os arquivos corrigidos antes de reenviar para reavaliação.',
            'readonly': True,
            'versao': None,
            'items': [],
        })

    return {'modo': 'reprovacao', 'grupos': grupos}
