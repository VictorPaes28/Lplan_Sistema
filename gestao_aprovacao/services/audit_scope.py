"""
Recorte de AuditEvent para Responsável Empresa (sem ver eventos globais de outras empresas).
"""
from __future__ import annotations

from django.db.models import Q, QuerySet

from audit.action_codes import AuditAction
from audit.models import AuditEvent
from gestao_aprovacao.models import Empresa, Obra, UserEmpresa


def responsavel_audit_empresa_ids(user) -> list[int]:
    return list(Empresa.objects.filter(responsavel=user, ativo=True).values_list('pk', flat=True))


def _payload_empresa_ids_vinculadas_overlap(payload, empresa_ids: set[int]) -> bool:
    if not isinstance(payload, dict) or not empresa_ids:
        return False
    raw = payload.get('empresa_ids_vinculadas') or []
    if not isinstance(raw, (list, tuple)):
        return False
    try:
        linked = {int(x) for x in raw if x is not None}
    except (TypeError, ValueError):
        return False
    return bool(linked & empresa_ids)


def filter_audit_events_for_responsavel(user, base: QuerySet | None = None) -> QuerySet:
    """
    Eventos onde o alvo/ator pertence ao universo da empresa ou o payload referencia empresa/obra/projeto
    vinculados às empresas sob responsabilidade do utilizador.
    """
    empresa_ids = responsavel_audit_empresa_ids(user)
    if not empresa_ids:
        return AuditEvent.objects.none()

    qs = base if base is not None else AuditEvent.objects.all()

    scoped_user_ids = list(
        UserEmpresa.objects.filter(empresa_id__in=empresa_ids, ativo=True).values_list(
            'usuario_id', flat=True
        )
    )
    obra_ids = list(Obra.objects.filter(empresa_id__in=empresa_ids).values_list('pk', flat=True))
    project_ids = [
        pid
        for pid in Obra.objects.filter(empresa_id__in=empresa_ids, project_id__isnull=False).values_list(
            'project_id', flat=True
        )
    ]

    q = Q(subject_user_id__in=scoped_user_ids) | Q(actor_id__in=scoped_user_ids)
    if empresa_ids:
        q |= Q(payload__empresa_id__in=empresa_ids)
        q |= Q(payload__before__empresa_id__in=empresa_ids)
        q |= Q(payload__after__empresa_id__in=empresa_ids)
    if obra_ids:
        q |= Q(payload__obra_id__in=obra_ids)
        q |= Q(payload__before__obra_id__in=obra_ids)
        q |= Q(payload__after__obra_id__in=obra_ids)
    if project_ids:
        q |= Q(payload__project_id__in=project_ids)

    matching_pk = set(qs.filter(q).values_list('pk', flat=True))
    empresa_set = set(empresa_ids)
    for row in qs.filter(action_code=AuditAction.USER_DELETED).values('pk', 'payload').iterator():
        if _payload_empresa_ids_vinculadas_overlap(row.get('payload'), empresa_set):
            matching_pk.add(row['pk'])

    return qs.filter(pk__in=matching_pk)


def responsavel_may_view_audit_event(user, event: AuditEvent) -> bool:
    return filter_audit_events_for_responsavel(user).filter(pk=event.pk).exists()
