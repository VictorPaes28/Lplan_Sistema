"""
Briefing operacional compacto — contexto automático para a IA WhatsApp.
Executado em Python antes de cada chamada OpenAI (não é tool da IA).
"""
from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from core.models import Project

from whatsapp_ia.ia_functions import (
    _dias_em_aberto_pedido,
    _frentes_ativas_project,
    _get_escopo_obras,
    _get_escopo_trackhub,
    _metricas_rdo_frequencia,
    _pedido_prazo_vencido,
    _project_ids_escopo,
    _queryset_workorders_escopo,
    _restricoes_totais_obra,
)

DIAS_RDO_ALERTA = 7
DIAS_PEDIDO_ALERTA = 7
TOP_PEDIDOS_CRITICOS = 8
TOP_OBRAS_RESTRICOES = 5


def _briefing_cache_key(usuario_wa) -> str:
    uid = usuario_wa.id if usuario_wa else 'anon'
    return f'wa_briefing:{uid}:{timezone.localdate()}'


def _briefing_cache_ttl() -> int:
    return int(getattr(settings, 'WHATSAPP_IA_BRIEFING_CACHE_TTL', 300))


def _rdos_atrasados_escopo(usuario_wa, hoje, dias_alerta=DIAS_RDO_ALERTA) -> list[dict]:
    project_ids = _project_ids_escopo(usuario_wa)
    projects = Project.objects.filter(
        is_active=True,
        id__in=project_ids,
    ).order_by('name')

    atrasados = []
    for project in projects:
        frentes = _frentes_ativas_project(project)
        segmentos = (
            [None] + [f.id for f in frentes]
            if frentes
            else ['todas']
        )
        pior_dias = None
        alerta = False
        nunca = False

        for seg in segmentos:
            metricas = _metricas_rdo_frequencia(
                project,
                front_id=seg,
                dias_sem_rdo_alerta=dias_alerta,
            )
            if metricas['nunca_teve_rdo']:
                nunca = True
                alerta = True
            if metricas['sem_rdo_recente']:
                alerta = True
                dias = metricas['dias_desde_ultimo']
                if dias is not None and (pior_dias is None or dias > pior_dias):
                    pior_dias = dias

        if alerta:
            item = {'obra': project.name}
            if nunca:
                item['nunca_teve_rdo'] = True
            if pior_dias is not None:
                item['dias_desde_ultimo'] = pior_dias
            atrasados.append(item)

    atrasados.sort(
        key=lambda x: (
            not x.get('nunca_teve_rdo'),
            -(x.get('dias_desde_ultimo') or 9999),
        ),
    )
    return atrasados


def _pedidos_criticos_escopo(usuario_wa, hoje, dias_alerta=DIAS_PEDIDO_ALERTA) -> list[dict]:
    qs = _queryset_workorders_escopo(usuario_wa).filter(
        status__in=['pendente', 'reaprovacao'],
    ).select_related('obra', 'front')

    criticos = []
    for w in qs:
        dias = _dias_em_aberto_pedido(w, hoje) or 0
        pv = _pedido_prazo_vencido(w, hoje)
        if dias > dias_alerta or pv:
            criticos.append({
                'codigo': w.codigo,
                'obra': w.obra.nome if w.obra else '-',
                'dias_em_aberto': dias,
                'prazo_vencido': pv,
            })

    criticos.sort(
        key=lambda x: (x['prazo_vencido'], x['dias_em_aberto']),
        reverse=True,
    )
    return criticos


def _restricoes_escopo(usuario_wa) -> dict:
    from gestao_aprovacao.models import Obra as ObraGestao

    escopo_ids = list(_get_escopo_obras(usuario_wa).values_list('id', flat=True))
    obras_gestao = ObraGestao.objects.filter(
        ativo=True,
        project__obra_mapa__id__in=escopo_ids,
    ).order_by('nome')

    total_abertas = 0
    total_vencidas = 0
    por_obra = []

    for obra_g in obras_gestao:
        stats = _restricoes_totais_obra(obra_g)
        total_abertas += stats['total_abertas']
        total_vencidas += stats['vencidas']
        if stats['total_abertas'] > 0:
            por_obra.append({
                'obra': obra_g.nome,
                'abertas': stats['total_abertas'],
                'vencidas': stats['vencidas'],
                'criticas_altas': stats['criticas_altas'],
            })

    por_obra.sort(key=lambda x: (-x['abertas'], x['obra']))
    return {
        'total': total_abertas,
        'vencidas': total_vencidas,
        'obras_mais_criticas': por_obra[:TOP_OBRAS_RESTRICOES],
    }


def _pendencias_vencidas_escopo(usuario_wa, hoje) -> dict:
    from trackhub.models import Pendencia

    escopo = _get_escopo_trackhub(usuario_wa)
    qs = Pendencia.objects.filter(
        obra__in=escopo,
        prazo__isnull=False,
        prazo__lt=hoje,
    ).exclude(
        status__in=['concluida', 'cancelada'],
    ).select_related('obra')

    total = qs.count()
    por_obra_map = {}
    for p in qs:
        nome = p.obra.nome if p.obra else '-'
        por_obra_map[nome] = por_obra_map.get(nome, 0) + 1

    por_obra = [
        {'obra': nome, 'qtd': qtd}
        for nome, qtd in sorted(
            por_obra_map.items(),
            key=lambda x: (-x[1], x[0]),
        )
    ]
    return {'total': total, 'por_obra': por_obra[:TOP_OBRAS_RESTRICOES]}


def _obras_com_alerta(
    nomes_obras: list[str],
    rdos: list[dict],
    pedidos: list[dict],
    restricoes_por_obra: list[dict],
    pendencias_por_obra: list[dict],
) -> set[str]:
    com_alerta = set()
    for r in rdos:
        com_alerta.add(r['obra'])
    for p in pedidos:
        com_alerta.add(p['obra'])
    for r in restricoes_por_obra:
        com_alerta.add(r['obra'])
    for p in pendencias_por_obra:
        com_alerta.add(p['obra'])
    return com_alerta


def _compute_briefing(usuario_wa) -> dict:
    hoje = timezone.localdate()
    obras_escopo = list(
        _get_escopo_obras(usuario_wa).order_by('nome').values_list('nome', flat=True),
    )

    rdos_atrasados = _rdos_atrasados_escopo(usuario_wa, hoje)
    pedidos_criticos = _pedidos_criticos_escopo(usuario_wa, hoje)
    restricoes = _restricoes_escopo(usuario_wa)
    pendencias = _pendencias_vencidas_escopo(usuario_wa, hoje)

    com_alerta = _obras_com_alerta(
        obras_escopo,
        rdos_atrasados,
        pedidos_criticos,
        restricoes['obras_mais_criticas'],
        pendencias['por_obra'],
    )
    obras_sem_alertas = [n for n in obras_escopo if n not in com_alerta]

    return {
        'data_referencia': str(hoje),
        'escopo': {
            'total_obras': len(obras_escopo),
            'obras': obras_escopo,
        },
        'alertas': {
            'rdos_atrasados': {
                'total': len(rdos_atrasados),
                'obras': rdos_atrasados[:TOP_OBRAS_RESTRICOES],
            },
            'pedidos_criticos': {
                'total': len(pedidos_criticos),
                'top': pedidos_criticos[:TOP_PEDIDOS_CRITICOS],
            },
            'restricoes_abertas': {
                'total': restricoes['total'],
                'vencidas': restricoes['vencidas'],
                'obras_mais_criticas': restricoes['obras_mais_criticas'],
            },
            'pendencias_vencidas': {
                'total': pendencias['total'],
                'por_obra': pendencias['por_obra'],
            },
        },
        'obras_sem_alertas': obras_sem_alertas,
    }


def gerar_briefing_operacional(usuario_wa=None, use_cache: bool = True) -> dict:
    """
    Snapshot compacto do estado operacional do escopo do usuário.
    Resultado cacheado por usuário/data (TTL configurável).
    """
    if use_cache:
        key = _briefing_cache_key(usuario_wa)
        cached = cache.get(key)
        if cached is not None:
            return cached

    briefing = _compute_briefing(usuario_wa)

    if use_cache:
        cache.set(key, briefing, _briefing_cache_ttl())

    return briefing


def invalidar_cache_briefing(usuario_wa=None) -> None:
    """Útil para testes ou invalidação manual."""
    cache.delete(_briefing_cache_key(usuario_wa))
