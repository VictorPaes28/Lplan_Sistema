"""
Expurgo por idade com base em AuditRetentionPolicy (fallback em código se não houver linha).
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from audit.models import AuditEvent, AuditRetentionPolicy

DEFAULT_AUDIT_EVENT_RETENTION_DAYS = 730
DEFAULT_USER_LOGIN_LOG_RETENTION_DAYS = 365


def _policy_days(key: str, default: int) -> int:
    try:
        p = AuditRetentionPolicy.objects.get(key=key)
        if p.retention_days is not None:
            return int(p.retention_days)
    except AuditRetentionPolicy.DoesNotExist:
        pass
    return default


def purge_audit_events_older_than(*, days: int | None = None, dry_run: bool = False) -> int:
    d = days if days is not None else _policy_days('audit_events', DEFAULT_AUDIT_EVENT_RETENTION_DAYS)
    cutoff = timezone.now() - timedelta(days=max(d, 1))
    qs = AuditEvent.objects.filter(created_at__lt=cutoff)
    n = qs.count()
    if not dry_run and n:
        qs.delete()
    return n


def purge_user_login_logs_older_than(*, days: int | None = None, dry_run: bool = False) -> int:
    from accounts.models import UserLoginLog

    d = days if days is not None else _policy_days('user_login_log', DEFAULT_USER_LOGIN_LOG_RETENTION_DAYS)
    cutoff = timezone.now() - timedelta(days=max(d, 1))
    qs = UserLoginLog.objects.filter(created_at__lt=cutoff)
    n = qs.count()
    if not dry_run and n:
        qs.delete()
    return n
