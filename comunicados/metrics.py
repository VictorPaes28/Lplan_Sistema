"""
Métricas de público-alvo e desempenho para comunicados.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model

from core.models import ProjectMember

User = get_user_model()


def get_eligible_user_ids(comunicado) -> set[int]:
    """
    Usuários ativos que, pela regra atual de público, deveriam poder ver o comunicado.
    """
    excl_u = set(comunicado.usuarios_excluidos.values_list('pk', flat=True))
    excl_g = set(comunicado.grupos_excluidos.values_list('pk', flat=True))
    perm_g = set(comunicado.grupos_permitidos.values_list('pk', flat=True))
    perm_u = set(comunicado.usuarios_permitidos.values_list('pk', flat=True))
    obra_proj = list(
        comunicado.obras_permitidas.exclude(project_id=None).values_list('project_id', flat=True)
    )
    obra_proj_set = set(obra_proj)
    member_uids = set()
    if obra_proj_set:
        member_uids = set(
            ProjectMember.objects.filter(project_id__in=obra_proj_set).values_list('user_id', flat=True)
        )

    eligible: set[int] = set()
    for u in User.objects.filter(is_active=True).prefetch_related('groups').iterator(chunk_size=500):
        if u.pk in excl_u:
            continue
        if excl_g and u.groups.filter(pk__in=excl_g).exists():
            continue
        if comunicado.publico_todos:
            eligible.add(u.pk)
            continue
        if perm_g and u.groups.filter(pk__in=perm_g).exists():
            eligible.add(u.pk)
            continue
        if u.pk in perm_u:
            eligible.add(u.pk)
            continue
        if obra_proj_set and u.pk in member_uids:
            eligible.add(u.pk)
            continue
    return eligible
