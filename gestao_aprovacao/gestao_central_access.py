"""Permissões de envio GestControll → Central de Aprovações."""
from __future__ import annotations

from accounts.groups import GRUPOS

from gestao_aprovacao.models import WorkOrder
from gestao_aprovacao.services.central_dispatch import workorder_dispatch_block_reason


def user_can_send_workorder_to_central(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=GRUPOS.ENVIAR_PARA_CENTRAL_APROVACOES).exists()


def workorder_can_offer_central_dispatch(workorder: WorkOrder, user) -> bool:
    """Pode exibir ação de envio (permissão + elegibilidade do pedido)."""
    if not user_can_send_workorder_to_central(user):
        return False
    return not workorder_dispatch_block_reason(workorder)
