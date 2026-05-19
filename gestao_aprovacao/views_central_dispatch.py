"""Views de envio do GestControll para a Central de Aprovações."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from gestao_aprovacao.gestao_central_access import (
    user_can_send_workorder_to_central,
    workorder_can_offer_central_dispatch,
)
from gestao_aprovacao.models import Attachment, GestaoCentralDispatch, WorkOrder
from gestao_aprovacao.services.central_dispatch import (
    GestaoCentralDispatchDuplicateError,
    GestaoCentralDispatchError,
    GestaoCentralNoFlowError,
    build_dispatch_snapshot,
    central_process_url_for_user,
    dispatch_workorder_to_central,
    workorder_dispatch_block_reason,
)


def _workorder_send_context(workorder, user, request):
    snapshot_preview = build_dispatch_snapshot(workorder, request=request)
    central = getattr(workorder, 'central_dispatch', None)
    central_url = None
    if central:
        central_url = central_process_url_for_user(user, central.approval_process_id)
    return {
        'workorder': workorder,
        'snapshot_preview': snapshot_preview,
        'attachments': Attachment.objects.filter(work_order=workorder).order_by('-created_at'),
        'block_reason': workorder_dispatch_block_reason(workorder),
        'central_dispatch': central,
        'central_process_url': central_url,
    }


@login_required
@require_http_methods(['GET', 'POST'])
def send_workorder_to_central(request, pk):
    workorder = get_object_or_404(
        WorkOrder.objects.select_related('obra', 'obra__project', 'criado_por').prefetch_related(
            'central_dispatch__approval_process'
        ),
        pk=pk,
    )

    if not user_can_send_workorder_to_central(request.user):
        return HttpResponseForbidden('Sem permissão para enviar pedidos à Central de Aprovações.')

    if request.method == 'POST':
        if not workorder_can_offer_central_dispatch(workorder, request.user):
            messages.error(
                request,
                workorder_dispatch_block_reason(workorder) or 'Envio não permitido para este pedido.',
            )
            return redirect('gestao:detail_workorder', pk=workorder.pk)

        send_comment = (request.POST.get('send_comment') or '').strip()
        try:
            dispatch = dispatch_workorder_to_central(
                workorder,
                user=request.user,
                send_comment=send_comment,
                request=request,
            )
            messages.success(
                request,
                f'Pedido enviado à Central de Aprovações (processo #{dispatch.approval_process_id}). '
                'Acompanhe na fila da Central; a decisão cabe ao aprovador configurado na alçada atual.',
            )
            if central_process_url_for_user(request.user, dispatch.approval_process_id):
                return redirect('workflow_aprovacao:pending')
            return redirect('gestao:detail_workorder', pk=workorder.pk)
        except GestaoCentralDispatchDuplicateError as e:
            messages.warning(request, str(e))
        except GestaoCentralNoFlowError as e:
            messages.error(request, str(e))
        except GestaoCentralDispatchError as e:
            messages.error(request, str(e))
        return redirect('gestao:detail_workorder', pk=workorder.pk)

    ctx = _workorder_send_context(workorder, request.user, request)
    if ctx['block_reason'] and not ctx['central_dispatch']:
        messages.info(request, ctx['block_reason'])

    return render(request, 'obras/central_send_confirm.html', ctx)
