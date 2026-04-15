"""Snapshots e registro de auditoria para alterações administrativas de usuário (GestControll/Central)."""

from __future__ import annotations

from audit.action_codes import AuditAction
from audit.recording import record_audit_event, summarize_user_admin_diff
from core.models import ProjectMember
from gestao_aprovacao.models import WorkOrderPermission


def snapshot_user_admin_state(user) -> dict:
    perms = list(WorkOrderPermission.objects.filter(usuario=user).values('obra_id', 'tipo_permissao', 'ativo'))
    pairs = sorted((p['obra_id'], p['tipo_permissao'], p['ativo']) for p in perms)
    return {
        'email': user.email or '',
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
        'is_active': user.is_active,
        'group_names': sorted(user.groups.values_list('name', flat=True)),
        'project_ids': sorted(ProjectMember.objects.filter(user=user).values_list('project_id', flat=True)),
        'work_order_permissions': pairs,
    }


def record_user_updated(request, actor, user, before: dict, after: dict, password_changed: bool) -> None:
    summary = summarize_user_admin_diff(before, after, password_changed)
    record_audit_event(
        actor=actor,
        subject_user=user,
        action_code=AuditAction.USER_UPDATED,
        summary=summary,
        payload={
            'before': before,
            'after': after,
            'password_changed': password_changed,
        },
        module='gestao',
        request=request,
    )


def record_user_created(request, actor, user, grupos: list, project_ids: list) -> None:
    record_audit_event(
        actor=actor,
        subject_user=user,
        action_code=AuditAction.USER_CREATED,
        summary=f'Usuário criado: {user.username}',
        payload={
            'username': user.username,
            'email': user.email,
            'group_names': grupos,
            'project_ids': project_ids,
        },
        module='gestao',
        request=request,
    )


def record_user_deleted(request, actor, snapshot: dict) -> None:
    record_audit_event(
        actor=actor,
        subject_user=None,
        action_code=AuditAction.USER_DELETED,
        summary=f'Usuário excluído: {snapshot.get("username", "?")}',
        payload=snapshot,
        module='gestao',
        request=request,
    )


