"""
Envio de pedidos aprovados do GestControll para a Central de Aprovações.
"""
from __future__ import annotations

from typing import Any, Optional

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from gestao_aprovacao.models import Attachment, GestaoCentralDispatch, StatusHistory, WorkOrder
from workflow_aprovacao.exceptions import NoFlowConfigurationError
from workflow_aprovacao.models import ProcessCategory, SyncStatus
from workflow_aprovacao.services.engine import ApprovalEngine

User = get_user_model()

GESTAO_EXTERNAL_ENTITY_TYPE = 'gestao_workorder'
GESTAO_EXTERNAL_SYSTEM = 'gestao'


class GestaoCentralDispatchError(Exception):
    """Erro de validação ou regra de negócio no envio à Central."""


class GestaoCentralDispatchDuplicateError(GestaoCentralDispatchError):
    """Pedido já possui envio registrado para a Central."""


class GestaoCentralNoFlowError(GestaoCentralDispatchError):
    """Não há fluxo configurado para obra + tipo."""


def category_for_workorder_tipo(tipo_solicitacao: str) -> Optional[ProcessCategory]:
    """Mesmo ``code`` do ``tipo_solicitacao`` (alinhado à Etapa A)."""
    code = (tipo_solicitacao or '').strip()
    if not code:
        return None
    return ProcessCategory.objects.filter(code=code, is_active=True).first()


def build_dispatch_snapshot(workorder: WorkOrder, *, request=None) -> dict[str, Any]:
    """Metadados e referências de anexos no momento do envio."""
    anexos = []
    for att in Attachment.objects.filter(work_order=workorder).order_by('pk'):
        url = ''
        if att.arquivo:
            try:
                url = att.arquivo.url
                if request and url and not url.startswith('http'):
                    url = request.build_absolute_uri(url)
            except Exception:
                url = ''
        enviado = att.enviado_por
        anexos.append(
            {
                'id': att.pk,
                'nome': att.get_nome_display(),
                'url': url,
                'uploaded_at': att.created_at.isoformat() if att.created_at else '',
                'versao_reaprovacao': att.versao_reaprovacao,
                'extensao': att.get_extensao(),
                'tamanho': att.get_tamanho_display(),
                'enviado_por': (
                    (enviado.get_full_name() or enviado.username) if enviado else ''
                ),
            }
        )
    criado = workorder.criado_por
    return {
        'work_order_id': workorder.pk,
        'codigo': workorder.codigo,
        'obra_codigo': workorder.obra.codigo if workorder.obra_id else '',
        'obra_nome': workorder.obra.nome if workorder.obra_id else '',
        'tipo_solicitacao': workorder.tipo_solicitacao,
        'tipo_solicitacao_display': workorder.get_tipo_solicitacao_display(),
        'nome_credor': workorder.nome_credor,
        'valor_estimado': str(workorder.valor_estimado) if workorder.valor_estimado is not None else None,
        'valor_medicao': str(workorder.valor_medicao) if workorder.valor_medicao is not None else None,
        'solicitante': (
            (criado.get_full_name() or criado.username) if criado else ''
        ),
        'solicitante_id': criado.pk if criado else None,
        'anexos': anexos,
        'dispatched_at': timezone.now().isoformat(),
    }


def workorder_dispatch_block_reason(workorder: WorkOrder) -> str:
    """Motivo pelo qual o envio não é permitido (string vazia = pode enviar)."""
    if workorder.status != 'aprovado':
        return 'Somente pedidos com status Aprovado podem ser enviados à Central.'
    if workorder.status in ('cancelado', 'reprovado'):
        return 'Pedidos cancelados ou reprovados não podem ser enviados à Central.'
    if GestaoCentralDispatch.objects.filter(work_order_id=workorder.pk).exists():
        return 'Este pedido já foi enviado à Central de Aprovações.'
    if not workorder.obra_id:
        return 'Pedido sem obra vinculada.'
    project = getattr(workorder.obra, 'project', None)
    if not project:
        return (
            'A obra deste pedido não está vinculada a um projeto do sistema. '
            'Sincronize a obra antes de enviar à Central.'
        )
    cat = category_for_workorder_tipo(workorder.tipo_solicitacao)
    if not cat:
        return (
            f'Não existe categoria de processo na Central para o tipo '
            f'«{workorder.get_tipo_solicitacao_display()}».'
        )
    return ''


def _summary_from_snapshot(snapshot: dict[str, Any]) -> str:
    lines = [
        f'Pedido GestControll: {snapshot.get("codigo", "")}',
        f'Credor: {snapshot.get("nome_credor", "")}',
        f'Tipo: {snapshot.get("tipo_solicitacao_display", "")}',
        f'Obra: {snapshot.get("obra_codigo", "")} — {snapshot.get("obra_nome", "")}',
    ]
    if snapshot.get('valor_medicao'):
        lines.append(f'Valor medição: {snapshot["valor_medicao"]}')
    elif snapshot.get('valor_estimado'):
        lines.append(f'Valor estimado: {snapshot["valor_estimado"]}')
    return '\n'.join(lines)


@transaction.atomic
def dispatch_workorder_to_central(
    workorder: WorkOrder,
    *,
    user: User,
    send_comment: str = '',
    request=None,
) -> GestaoCentralDispatch:
    """
    Cria processo na Central e registo de envio (transação atómica, com lock no pedido).
    """
    if not user or not user.is_authenticated:
        raise GestaoCentralDispatchError('Usuário não autenticado.')

    wo = WorkOrder.objects.select_for_update().select_related('obra', 'obra__project', 'criado_por').get(
        pk=workorder.pk
    )

    block = workorder_dispatch_block_reason(wo)
    if block:
        if 'já foi enviado' in block:
            raise GestaoCentralDispatchDuplicateError(block)
        raise GestaoCentralDispatchError(block)

    project = wo.obra.project
    category = category_for_workorder_tipo(wo.tipo_solicitacao)
    if not category:
        raise GestaoCentralDispatchError(
            f'Não existe categoria na Central para o tipo «{wo.get_tipo_solicitacao_display()}».'
        )

    snapshot = build_dispatch_snapshot(wo, request=request)
    title = f'GestControll {wo.codigo} — {wo.get_tipo_solicitacao_display()}'
    summary = _summary_from_snapshot(snapshot)

    try:
        process = ApprovalEngine.start(
            project=project,
            category=category,
            initiated_by=user,
            title=title,
            summary=summary,
            content_object=wo,
            external_entity_type=GESTAO_EXTERNAL_ENTITY_TYPE,
            external_id=str(wo.pk),
            sync_status=SyncStatus.NOT_APPLICABLE,
            external_payload=snapshot,
        )
        if process.external_system != GESTAO_EXTERNAL_SYSTEM:
            process.external_system = GESTAO_EXTERNAL_SYSTEM
            process.save(update_fields=['external_system', 'updated_at'])
    except NoFlowConfigurationError:
        raise GestaoCentralNoFlowError(
            'Não existe fluxo de aprovação configurado para esta obra e tipo de solicitação. '
            'Peça ao administrador da Central para configurar o fluxo.'
        ) from None

    dispatch = GestaoCentralDispatch.objects.create(
        work_order=wo,
        approval_process=process,
        sent_by=user,
        send_comment=(send_comment or '').strip(),
        snapshot_payload=snapshot,
    )

    obs_parts = [
        f'Enviado à Central de Aprovações (processo #{process.pk}).',
    ]
    if send_comment.strip():
        obs_parts.append(f'Observação: {send_comment.strip()}')
    StatusHistory.objects.create(
        work_order=wo,
        status_anterior=wo.status,
        status_novo=wo.status,
        alterado_por=user,
        observacao=' '.join(obs_parts),
    )

    return dispatch


def user_can_view_central_process_link(user) -> bool:
    from workflow_aprovacao.access import user_in_any_workflow_group

    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user_in_any_workflow_group(user)


def central_process_url_for_user(user, process_pk: int) -> Optional[str]:
    if not user_can_view_central_process_link(user):
        return None
    return reverse('workflow_aprovacao:process_detail', kwargs={'pk': process_pk})
