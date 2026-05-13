"""
Criação centralizada de core.Notification (sino + centro /notifications/).
Marcação em lote por event_key ou por utilizador.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model

# Tipos Core ligados a pedidos ainda na fila de aprovação (marcar lidas ao aprovar/reprovar).
CORE_TIPOS_PEDIDO_FILA_APROVACAO = (
    'pedido_criado',
    'pedido_reenviado',
    'pedido_atualizado',
)


def criar_notificacao(usuario_ou_lista, tipo, titulo, mensagem, url='', event_key=''):
    """
    Cria core.Notification para um usuário ou lista/queryset de usuários.

    usuario_ou_lista: User, lista, tuple, set ou queryset de Users
    url: URL direta para o item (ex.: /gestao/pedidos/42/)
    event_key: chave estável do recurso (ex.: gestao:wo:42) para marcar lidas depois
    """
    from core.models import Notification

    User = get_user_model()

    if usuario_ou_lista is None:
        return

    if isinstance(usuario_ou_lista, str):
        return

    if isinstance(usuario_ou_lista, User):
        usuarios = [usuario_ou_lista]
    elif isinstance(usuario_ou_lista, (list, tuple, set)):
        usuarios = list(usuario_ou_lista)
    else:
        usuarios = list(usuario_ou_lista)

    titulo_safe = (titulo or '')[:255]
    ek = (event_key or '')[:160]
    notificacoes = []
    seen_ids = set()
    for user in usuarios:
        if not user or not getattr(user, 'is_active', False):
            continue
        uid = getattr(user, 'pk', None)
        if uid is not None and uid in seen_ids:
            continue
        if uid is not None:
            seen_ids.add(uid)
        notificacoes.append(
            Notification(
                user=user,
                notification_type=tipo,
                title=titulo_safe,
                message=mensagem or '',
                related_url=(url or '')[:500],
                event_key=ek,
            )
        )
    if notificacoes:
        Notification.objects.bulk_create(notificacoes)


def marcar_lidas_por_event_key(event_key: str, notification_types=None) -> int:
    """Marca como lidas todas as notificações com este event_key (todos os usuários)."""
    from core.models import Notification

    if not (event_key or '').strip():
        return 0
    qs = Notification.objects.filter(is_read=False, event_key=event_key.strip())
    if notification_types:
        qs = qs.filter(notification_type__in=notification_types)
    return qs.update(is_read=True)


def marcar_lidas_para_usuario_event_key(user, event_key: str, notification_types=None) -> int:
    """Marca como lidas as notificações do usuário para um event_key."""
    from core.models import Notification

    if not user or not getattr(user, 'pk', None):
        return 0
    if not (event_key or '').strip():
        return 0
    qs = Notification.objects.filter(
        user=user, is_read=False, event_key=event_key.strip()
    )
    if notification_types:
        qs = qs.filter(notification_type__in=notification_types)
    return qs.update(is_read=True)


def marcar_lidas_por_event_key_etapa_trackhub(etapa_pk: int) -> int:
    """Após conclusão ou alerta de prazo resolvido por etapa TrackHub."""
    from core.models import Notification

    key = f'trackhub:etapa:{etapa_pk}'
    return Notification.objects.filter(is_read=False, event_key=key).update(is_read=True)
