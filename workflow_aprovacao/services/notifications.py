from __future__ import annotations

import logging
from typing import Optional

from django.utils import timezone

from workflow_aprovacao.models import ApprovalHistoryEntry, HistoryAction

logger = logging.getLogger(__name__)


def _normalize_phone(raw: str) -> str:
    return ''.join(ch for ch in (raw or '') if ch.isdigit())


def _send_whatsapp(*, phone: str, message: str) -> tuple[bool, str]:
    """
    Adapter mínimo para WhatsApp.
    Nesta fase fica plugável por provider externo sem quebrar a regra de negócio.
    """
    normalized = _normalize_phone(phone)
    if len(normalized) < 10:
        return False, 'telefone inválido'
    logger.info('workflow_whatsapp_dispatch phone=%s message=%s', normalized, message)
    return True, 'queued'


def _send_email(*, email: str, subject: str, message: str) -> tuple[bool, str]:
    try:
        from django.core.mail import send_mail
    except Exception:
        return False, 'mail_backend_unavailable'
    count = send_mail(
        subject=subject,
        message=message,
        from_email=None,
        recipient_list=[email],
        fail_silently=True,
    )
    return (count > 0), 'sent' if count > 0 else 'not_sent'


def notify_external_invite(*, process, target_name: str, email: str, phone_whatsapp: str, access_url: str) -> dict:
    body = (
        f'Olá, {target_name}. Você foi indicado como responsável externo para análise/assinatura '
        f'do pedido {process.title or f"# {process.pk}"} da obra {process.project.code}. '
        f'Acesse: {access_url}'
    )
    channel = 'none'
    success = False
    detail = ''
    if (phone_whatsapp or '').strip():
        success, detail = _send_whatsapp(phone=phone_whatsapp, message=body)
        channel = 'whatsapp'
    if not success and (email or '').strip():
        success, detail = _send_email(
            email=email,
            subject='Convite para assinatura de pedido',
            message=body,
        )
        channel = 'email'
    payload = {
        'channel': channel,
        'success': bool(success),
        'detail': detail,
        'at': timezone.now().isoformat(),
    }
    ApprovalHistoryEntry.objects.create(
        process=process,
        step=process.current_step,
        step_sequence_snapshot=process.current_step.sequence if process.current_step else None,
        actor=None,
        action=HistoryAction.COMMENT,
        comment='Convite de acesso enviado ao participante externo.'
        if success
        else 'Tentativa de convite ao participante externo sem sucesso.',
        previous_status=process.status,
        new_status=process.status,
        payload={'notification': payload},
    )
    return payload
