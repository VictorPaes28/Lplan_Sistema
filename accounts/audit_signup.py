"""Registro de auditoria para fluxo de solicitação/aprovação de cadastro (Central e formulário público)."""

from __future__ import annotations

from typing import Any

from audit.action_codes import AuditAction
from audit.recording import record_audit_event


def _normalize_project_ids(project_ids: list[Any] | None) -> list[int]:
    out: list[int] = []
    if not project_ids:
        return out
    for pid in project_ids:
        try:
            v = int(pid)
        except (TypeError, ValueError):
            continue
        if v not in out:
            out.append(v)
    return sorted(out)


def record_signup_request_internal(request, actor, signup_req) -> None:
    record_audit_event(
        actor=actor,
        subject_user=None,
        action_code=AuditAction.USER_SIGNUP_REQUEST_INTERNAL,
        summary=f'Solicitação de cadastro interna: {signup_req.email}',
        payload={
            'signup_request_id': signup_req.pk,
            'email': signup_req.email,
            'full_name': signup_req.full_name,
            'requested_groups': signup_req.requested_groups,
            'requested_project_ids': signup_req.requested_project_ids,
            'origem': signup_req.origem,
        },
        module='accounts',
        request=request,
    )


def record_signup_request_public(request, signup_req) -> None:
    actor = signup_req.requested_by if signup_req.requested_by_id else None
    record_audit_event(
        actor=actor,
        subject_user=None,
        action_code=AuditAction.USER_SIGNUP_REQUEST_PUBLIC,
        summary=f'Solicitação de cadastro (público): {signup_req.email}',
        payload={
            'signup_request_id': signup_req.pk,
            'email': signup_req.email,
            'full_name': signup_req.full_name,
            'requested_project_ids': signup_req.requested_project_ids,
            'origem': signup_req.origem,
        },
        module='accounts',
        request=request,
    )


def record_signup_approved(
    request,
    actor,
    signup_req,
    created_user,
    selected_groups: list[str],
    selected_project_ids: list[Any],
) -> None:
    record_audit_event(
        actor=actor,
        subject_user=created_user,
        action_code=AuditAction.USER_SIGNUP_APPROVED,
        summary=f'Cadastro aprovado na Central: {created_user.username} ({signup_req.email})',
        payload={
            'signup_request_id': signup_req.pk,
            'email': signup_req.email,
            'full_name': signup_req.full_name,
            'approved_groups': list(selected_groups),
            'approved_project_ids': _normalize_project_ids(selected_project_ids),
            'created_username': created_user.username,
        },
        module='accounts',
        request=request,
    )


def record_signup_rejected(request, actor, signup_req, rejection_reason: str) -> None:
    record_audit_event(
        actor=actor,
        subject_user=None,
        action_code=AuditAction.USER_SIGNUP_REJECTED,
        summary=f'Cadastro rejeitado na Central: {signup_req.email}',
        payload={
            'signup_request_id': signup_req.pk,
            'email': signup_req.email,
            'full_name': signup_req.full_name,
            'rejection_reason': (rejection_reason or '')[:2000],
            'requested_groups': signup_req.requested_groups,
            'requested_project_ids': signup_req.requested_project_ids,
        },
        module='accounts',
        request=request,
    )
