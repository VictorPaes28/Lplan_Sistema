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

from core.models import ProjectMember, ProjectOwner

from .models import (
    Comunicado,
    ComunicadoVisualizacao,
    Prioridade,
    PublicoEscopoCriterios,
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
    - publico_todos=True → qualquer utilizador autenticado (antes de exclusões e restrição de perfil).
    - publico_todos=False → critérios permitidos combinados por publico_escopo_criterios (OU ou E).
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

    tem_g = bool(perm_g)
    tem_u = bool(permitidos)
    tem_p = bool(obras_proj)
    ok_g = bool(user_group_ids & perm_g) if tem_g else None
    ok_u = user.pk in permitidos if tem_u else None
    ok_p = bool(user_project_ids & obras_proj) if tem_p else None

    if c.publico_escopo_criterios == PublicoEscopoCriterios.TODOS:
        partes = [x for x in (ok_g, ok_u, ok_p) if x is not None]
        ok = all(partes) if partes else False
    else:
        ok = any(x is True for x in (ok_g, ok_u, ok_p))

    if settings.DEBUG:
        logger.debug(
            'comunicados: elegibilidade comunicado=%s user=%s ok=%s publico_todos=%s escopo=%s perm_g=%s '
            'permitidos_u=%s obras_proj=%s user_g=%s user_proj=%s',
            c.pk,
            user.pk,
            ok,
            c.publico_todos,
            c.publico_escopo_criterios,
            perm_g,
            permitidos,
            obras_proj,
            user_group_ids,
            user_project_ids,
        )
    return ok


def _usuario_excluido(user, c: Comunicado, user_group_ids: set[int], user_project_ids: set[int]) -> bool:
    if user.pk in {u.pk for u in c.usuarios_excluidos.all()}:
        return True
    excl_g = {g.pk for g in c.grupos_excluidos.all()}
    if user_group_ids & excl_g:
        return True
    excl_proj: set[int] = set()
    for obra in c.obras_excluidas.all():
        pid = obra.project_id
        if pid:
            excl_proj.add(pid)
    if excl_proj and user_project_ids & excl_proj:
        return True
    return False


def _passa_regra_exibicao(c: Comunicado, vis: ComunicadoVisualizacao | None, now, hoje) -> bool:
    if vis and vis.status_final == StatusFinalVisualizacao.IGNORADO:
        return False

    # Com tipo "Sempre", os ramos abaixo devolviam True sem olhar para a ação já feita — gerava loop no modal.
    if c.tipo_conteudo == TipoConteudo.FORMULARIO and vis and vis.respondeu:
        return False
    if (
        c.tipo_conteudo
        in (TipoConteudo.TEXTO, TipoConteudo.IMAGEM, TipoConteudo.IMAGEM_LINK)
        and c.exige_confirmacao
        and vis
        and vis.confirmou_leitura
    ):
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

    # Clientes donos de obra nunca recebem comunicados
    if ProjectOwner.objects.filter(user=user).exists():
        return []

    base_ids = list(_candidatos_base_queryset().values_list('pk', flat=True))
    if not base_ids:
        return []

    candidatos = (
        Comunicado.objects.filter(pk__in=base_ids)
        .prefetch_related(
            'imagens',
            'grupos_permitidos',
            'usuarios_permitidos',
            'obras_permitidas',
            'grupos_excluidos',
            'usuarios_excluidos',
            'obras_excluidas',
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
        if _usuario_excluido(user, c, user_group_ids, user_project_ids):
            continue
        if not _usuario_em_publico_alvo(user, c, user_group_ids, user_project_ids):
            continue
        vis = vis_map.get(c.pk)
        # Fechou=True evita reabrir na mesma sessão (e impede loop quando a API volta a devolver o mesmo pendente).
        # "Mostrar após fechar" reabre nessa sessão para outros tipos de exibição — exceto SEMPRE, que só volta
        # após novo login (`reset_comunicados_sempre_fechou` em accounts.signals).
        if vis and vis.fechou:
            if c.tipo_exibicao == TipoExibicao.SEMPRE or not c.mostrar_apos_fechar:
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
