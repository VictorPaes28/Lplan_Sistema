"""
Auditoria de cadastros Empresa/Obra (GestControll).

Payload padronizado (v1):
- schema: 'empresa_v1' | 'obra_v1'
- entity: 'empresa' | 'obra'
- *_id: chave primária para deep links e relatórios
- demais campos: snapshot dos atributos rastreados
"""

from __future__ import annotations

from audit.action_codes import AuditAction
from audit.recording import record_audit_event


def snapshot_empresa(empresa) -> dict:
    return {
        'schema': 'empresa_v1',
        'entity': 'empresa',
        'empresa_id': empresa.pk,
        'codigo': empresa.codigo,
        'nome': empresa.nome,
        'email': empresa.email or '',
        'telefone': empresa.telefone or '',
        'ativo': empresa.ativo,
        'responsavel_id': empresa.responsavel_id,
    }


def snapshot_obra(obra) -> dict:
    return {
        'schema': 'obra_v1',
        'entity': 'obra',
        'obra_id': obra.pk,
        'codigo': obra.codigo,
        'nome': obra.nome,
        'descricao': (obra.descricao or '')[:500],
        'email_obra': obra.email_obra or '',
        'ativo': obra.ativo,
        'empresa_id': obra.empresa_id,
        'project_id': obra.project_id,
    }


def _diff_keys(before: dict, after: dict) -> list[str]:
    keys = set(before) | set(after)
    ignore = {'schema'}
    return sorted(k for k in keys if k not in ignore and before.get(k) != after.get(k))


def record_empresa_created(request, actor, empresa) -> None:
    snap = snapshot_empresa(empresa)
    record_audit_event(
        actor=actor,
        subject_user=None,
        action_code=AuditAction.EMPRESA_CREATED,
        summary=f'Empresa criada: {empresa.codigo} — {empresa.nome}',
        payload=snap,
        module='gestao',
        request=request,
    )


def record_empresa_updated(request, actor, before: dict, after: dict) -> None:
    changed = _diff_keys(before, after)
    summary = f'Empresa {after.get("codigo", "?")} atualizada'
    if changed:
        summary += ': ' + ', '.join(changed)
    record_audit_event(
        actor=actor,
        subject_user=None,
        action_code=AuditAction.EMPRESA_UPDATED,
        summary=summary[:500],
        payload={'before': before, 'after': after, 'changed_fields': changed},
        module='gestao',
        request=request,
    )


def record_obra_created(request, actor, obra) -> None:
    snap = snapshot_obra(obra)
    record_audit_event(
        actor=actor,
        subject_user=None,
        action_code=AuditAction.OBRA_CREATED,
        summary=f'Obra criada: {obra.codigo} — {obra.nome}',
        payload=snap,
        module='gestao',
        request=request,
    )


def record_obra_updated(request, actor, before: dict, after: dict) -> None:
    changed = _diff_keys(before, after)
    summary = f'Obra {after.get("codigo", "?")} atualizada'
    if changed:
        summary += ': ' + ', '.join(changed)
    record_audit_event(
        actor=actor,
        subject_user=None,
        action_code=AuditAction.OBRA_UPDATED,
        summary=summary[:500],
        payload={'before': before, 'after': after, 'changed_fields': changed},
        module='gestao',
        request=request,
    )
