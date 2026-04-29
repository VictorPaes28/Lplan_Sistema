"""
Métricas de público-alvo e desempenho para comunicados.
"""
from __future__ import annotations

from collections import defaultdict

from django.contrib.auth import get_user_model

from core.models import ProjectMember

from .models import PublicoEscopoCriterios

User = get_user_model()


def get_eligible_user_ids(comunicado) -> set[int]:
    """
    Usuários ativos que, pela regra atual de público, deveriam poder ver o comunicado.
    Espelha a mesma lógica que `listar_comunicados_pendentes` (audiência + exclusões).
    """
    excl_u = set(comunicado.usuarios_excluidos.values_list('pk', flat=True))
    excl_g = set(comunicado.grupos_excluidos.values_list('pk', flat=True))
    excl_obras_proj = set(
        comunicado.obras_excluidas.exclude(project_id=None).values_list('project_id', flat=True)
    )
    perm_g = set(comunicado.grupos_permitidos.values_list('pk', flat=True))
    perm_u = set(comunicado.usuarios_permitidos.values_list('pk', flat=True))
    obra_proj_set = set(
        comunicado.obras_permitidas.exclude(project_id=None).values_list('project_id', flat=True)
    )

    all_proj = obra_proj_set | excl_obras_proj
    user_projects: dict[int, set[int]] = defaultdict(set)
    if all_proj:
        for uid, pid in ProjectMember.objects.filter(project_id__in=all_proj).values_list(
            'user_id', 'project_id'
        ):
            user_projects[uid].add(pid)

    eligible: set[int] = set()
    for u in User.objects.filter(is_active=True).prefetch_related('groups').iterator(chunk_size=500):
        if u.pk in excl_u:
            continue
        if excl_g and u.groups.filter(pk__in=excl_g).exists():
            continue

        user_g = set(u.groups.values_list('pk', flat=True))
        u_proj = user_projects.get(u.pk, set())
        if excl_obras_proj and u_proj & excl_obras_proj:
            continue

        if comunicado.publico_todos:
            pass_pub = True
        else:
            tem_g = bool(perm_g)
            tem_u = bool(perm_u)
            tem_p = bool(obra_proj_set)
            if not (tem_g or tem_u or tem_p):
                continue
            ok_g = bool(user_g & perm_g) if tem_g else None
            ok_u = u.pk in perm_u if tem_u else None
            ok_p = bool(u_proj & obra_proj_set) if tem_p else None
            if comunicado.publico_escopo_criterios == PublicoEscopoCriterios.TODOS:
                partes = [x for x in (ok_g, ok_u, ok_p) if x is not None]
                pass_pub = all(partes) if partes else False
            else:
                pass_pub = any(x is True for x in (ok_g, ok_u, ok_p))

        if not pass_pub:
            continue

        eligible.add(u.pk)
    return eligible
