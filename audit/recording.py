from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from audit.models import AuditEvent


def _request_meta(request: HttpRequest | None) -> tuple[str | None, str]:
    if not request:
        return None, ''
    ip = None
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        ip = xff.split(',')[0].strip()
    if not ip:
        ip = request.META.get('REMOTE_ADDR')
    ua = (request.META.get('HTTP_USER_AGENT') or '')[:256]
    return ip, ua


def get_request_client_meta(request: HttpRequest | None) -> tuple[str | None, str]:
    """IP (primeiro X-Forwarded-For ou REMOTE_ADDR) e User-Agent truncado (LGPD / trilho de acesso)."""
    return _request_meta(request)


def record_audit_event(
    *,
    actor,
    action_code: str,
    summary: str,
    subject_user=None,
    payload: dict[str, Any] | None = None,
    module: str = 'gestao',
    request: HttpRequest | None = None,
) -> AuditEvent:
    """
    Persiste um evento de auditoria. Deve ser chamado após a operação ter sucesso
    (ou imediatamente antes de delete irreversível, com snapshot no payload).
    """
    ip, ua = _request_meta(request)
    return AuditEvent.objects.create(
        actor=actor if getattr(actor, 'pk', None) else None,
        subject_user=subject_user if subject_user and getattr(subject_user, 'pk', None) else None,
        action_code=action_code,
        module=module,
        summary=summary[:500],
        payload=payload or {},
        ip_address=ip,
        user_agent=ua,
    )


def summarize_user_admin_diff(before: dict, after: dict, password_changed: bool) -> str:
    parts = []
    if before.get('email') != after.get('email'):
        parts.append('e-mail')
    if before.get('first_name') != after.get('first_name') or before.get('last_name') != after.get('last_name'):
        parts.append('nome')
    if before.get('group_names') != after.get('group_names'):
        parts.append('grupos')
    if before.get('project_ids') != after.get('project_ids'):
        parts.append('projetos (Diário)')
    if before.get('work_order_permissions') != after.get('work_order_permissions'):
        parts.append('permissões por obra (GestControll)')
    if password_changed:
        parts.append('senha')
    if not parts:
        return 'Atualização administrativa (sem diferenças detectadas no snapshot)'
    return 'Alterou: ' + ', '.join(parts)
