"""
Regras de filtragem e pendentes para comunicados administrativos.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from core.models import ProjectMember

from .models import (
    Comunicado,
    ComunicadoVisualizacao,
    Prioridade,
    StatusFinalVisualizacao,
    TipoConteudo,
    TipoExibicao,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

logger = logging.getLogger(__name__)

PRIORIDADE_ORDEM = {
    Prioridade.CRITICA: 0,
    Prioridade.ALTA: 1,
    Prioridade.NORMAL: 2,
    Prioridade.BAIXA: 3,
}


def _agora():
    return timezone.now()


def _passa_janela_temporal(c: Comunicado, now) -> bool:
    if c.data_inicio and now < c.data_inicio:
        return False
    if c.data_fim and now > c.data_fim:
        return False
    if c.dias_ativo is not None and c.data_inicio is not None:
        if now > c.data_inicio + timedelta(days=int(c.dias_ativo)):
            return False
    return True


def _usuario_em_publico_alvo(user, c: Comunicado, user_group_ids: set[int], user_project_ids: set[int]) -> bool:
    """
    - publico_todos=True → qualquer utilizador autenticado (exceto regras de exclusão antes).
    - publico_todos=False → o utilizador tem de coincidir com pelo menos um critério permitido.
      Se não houver nenhum grupo/usuário/obra permitidos definidos, ninguém é elegível.
    """
    if c.publico_todos:
        return True

    perm_g = {g.pk for g in c.grupos_permitidos.all()}
    permitidos = {u.pk for u in c.usuarios_permitidos.all()}
    obras_proj: set[int] = set()
    for obra in c.obras_permitidas.all():
        pid = obra.project_id
        if pid:
            obras_proj.add(pid)

    tem_escopo = bool(perm_g or permitidos or obras_proj)
    if not tem_escopo:
        if settings.DEBUG:
            logger.debug(
                'comunicados: comunicado %s publico_todos=False sem critérios permitidos → ninguém elegível',
                c.pk,
            )
        return False

    ok = False
    if user_group_ids & perm_g:
        ok = True
    elif user.pk in permitidos:
        ok = True
    elif user_project_ids & obras_proj:
        ok = True

    if settings.DEBUG:
        logger.debug(
            'comunicados: elegibilidade comunicado=%s user=%s ok=%s publico_todos=%s perm_g=%s '
            'permitidos_u=%s obras_proj=%s user_g=%s user_proj=%s',
            c.pk,
            user.pk,
            ok,
            c.publico_todos,
            perm_g,
            permitidos,
            obras_proj,
            user_group_ids,
            user_project_ids,
        )
    return ok


def _usuario_excluido(user, c: Comunicado, user_group_ids: set[int]) -> bool:
    if user.pk in {u.pk for u in c.usuarios_excluidos.all()}:
        return True
    excl_g = {g.pk for g in c.grupos_excluidos.all()}
    return bool(user_group_ids & excl_g)


def _passa_regra_exibicao(c: Comunicado, vis: ComunicadoVisualizacao | None, now, hoje) -> bool:
    if vis and vis.status_final == StatusFinalVisualizacao.IGNORADO:
        return False

    # Com tipo "Sempre", os ramos abaixo devolviam True sem olhar para a ação já feita — gerava loop no modal.
    if c.tipo_conteudo == TipoConteudo.FORMULARIO and vis and vis.respondeu:
        return False
    if c.tipo_conteudo == TipoConteudo.CONFIRMACAO and vis and vis.confirmou_leitura:
        return False

    tipo = c.tipo_exibicao

    if tipo == TipoExibicao.SEMPRE:
        return True

    if tipo == TipoExibicao.UMA_VEZ:
        if vis is None:
            return True
        return vis.total_visualizacoes == 0

    if tipo == TipoExibicao.UMA_VEZ_POR_DIA:
        if vis is None:
            return True
        ultima = vis.ultima_visualizacao
        if ultima is None:
            return True
        dia_ultima = timezone.localtime(ultima).date()
        return dia_ultima < hoje

    if tipo == TipoExibicao.ATE_CONFIRMAR:
        if vis is None:
            return True
        return not vis.confirmou_leitura

    if tipo == TipoExibicao.ATE_RESPONDER:
        if vis is None:
            return True
        return not vis.respondeu

    if tipo == TipoExibicao.X_VEZES:
        if c.max_exibicoes_por_usuario is None:
            return False
        total = vis.total_visualizacoes if vis else 0
        return total < c.max_exibicoes_por_usuario

    if tipo == TipoExibicao.X_DIAS:
        return True

    return False


def _candidatos_base_queryset():
    now = _agora()
    return (
        Comunicado.objects.filter(ativo=True, abrir_automaticamente=True)
        .filter(Q(data_inicio__isnull=True) | Q(data_inicio__lte=now))
        .filter(Q(data_fim__isnull=True) | Q(data_fim__gte=now))
    )


def listar_comunicados_pendentes(user) -> list[Comunicado]:
    """
    Lista todos os comunicados que devem ser exibidos para o usuário, em ordem de prioridade.
    """
    now = _agora()
    hoje = timezone.localdate()

    user_group_ids = set(user.groups.values_list('pk', flat=True))
    user_project_ids = set(
        ProjectMember.objects.filter(user=user).values_list('project_id', flat=True)
    )

    base_ids = list(_candidatos_base_queryset().values_list('pk', flat=True))
    if not base_ids:
        return []

    candidatos = (
        Comunicado.objects.filter(pk__in=base_ids)
        .prefetch_related(
            'grupos_permitidos',
            'usuarios_permitidos',
            'obras_permitidas',
            'grupos_excluidos',
            'usuarios_excluidos',
        )
        .order_by('pk')
    )

    vis_map = {
        v.comunicado_id: v
        for v in ComunicadoVisualizacao.objects.filter(usuario=user, comunicado_id__in=base_ids)
    }

    pendentes: list[Comunicado] = []
    for c in candidatos:
        if not _passa_janela_temporal(c, now):
            continue
        if _usuario_excluido(user, c, user_group_ids):
            continue
        if not _usuario_em_publico_alvo(user, c, user_group_ids, user_project_ids):
            continue
        vis = vis_map.get(c.pk)
        # Já fechou o modal e o comunicado não pede "mostrar após fechar" → não voltar a exibir (evita reabrir ao dar POST fechou).
        if vis and vis.fechou and not c.mostrar_apos_fechar:
            continue
        if not _passa_regra_exibicao(c, vis, now, hoje):
            continue
        pendentes.append(c)

    pendentes.sort(key=lambda x: (PRIORIDADE_ORDEM.get(x.prioridade, 99), x.pk))
    return pendentes


def contar_pendentes(user) -> int:
    return len(listar_comunicados_pendentes(user))


def primeiro_pendente_e_total(user):
    lista = listar_comunicados_pendentes(user)
    if not lista:
        return None, 0
    return lista[0], len(lista)
