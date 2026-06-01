"""Views de envio do GestControll para a Central de Aprovações."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_http_methods

from gestao_aprovacao.gestao_central_access import (
    user_can_send_workorder_to_central,
    workorder_can_offer_central_dispatch,
)
from gestao_aprovacao.models import WorkOrder
from gestao_aprovacao.services.central_dispatch import (
    GestaoCentralDispatchError,
    manual_request_url_for_workorder,
    workorder_dispatch_block_reason,
)


@login_required
@require_http_methods(['GET', 'POST'])
def send_workorder_to_central(request, pk):
    """
    Redireciona para «Novo pedido» na Central (/aprovacoes/novo/) com dados do GestControll.
    O processo só é criado quando o usuário concluir o formulário na Central (fonte única).
    """
    workorder = get_object_or_404(
        WorkOrder.objects.select_related('obra', 'obra__project', 'criado_por').prefetch_related(
            'central_dispatch__approval_process'
        ),
        pk=pk,
    )

    if not user_can_send_workorder_to_central(request.user):
        return HttpResponseForbidden('Sem permissão para enviar pedidos à Central de Aprovações.')

    block = workorder_dispatch_block_reason(workorder)
    if block and not getattr(workorder, 'central_dispatch', None):
        messages.error(request, block)
        return redirect('gestao:detail_workorder', pk=workorder.pk)

    if not workorder_can_offer_central_dispatch(workorder, request.user):
        messages.error(
            request,
            block or 'Envio não permitido para este pedido.',
        )
        return redirect('gestao:detail_workorder', pk=workorder.pk)

    try:
        target_url = manual_request_url_for_workorder(workorder)
    except GestaoCentralDispatchError as exc:
        messages.error(request, str(exc))
        return redirect('gestao:detail_workorder', pk=workorder.pk)

    messages.info(
        request,
        f'Complete o pedido na Central para enviar {workorder.codigo}. '
        'Revise os dados, terceirizados e anexos antes de confirmar.',
    )
    return redirect(target_url)
