"""Filtros reutilizáveis do Mapa de Engenharia (suprimentos)."""
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from suprimentos.models import ItemMapa, mapa_suprimentos_manual


def get_mapa_filter_params(request):
    """Extrai parâmetros de filtro do request GET."""
    return {
        'categoria': request.GET.get('categoria', ''),
        'local_id': request.GET.get('local', ''),
        'prioridade': request.GET.get('prioridade', ''),
        'status': request.GET.get('status', ''),
        'pendencia': request.GET.get('pendencia', ''),
        'search': request.GET.get('search', ''),
        'quick': request.GET.get('quick', ''),
    }


def apply_mapa_engenharia_filters(itens, request, obra_id, manual):
    """
    Aplica filtros de busca, categoria, local, prioridade, pendência, status e quick filters.
    Retorna queryset (modo manual / pós-filtro SQL) ou queryset reconstruído (modo Sienge).
    """
    params = get_mapa_filter_params(request)
    categoria = params['categoria']
    local_id = params['local_id']
    prioridade = params['prioridade']
    status_filtro = params['status']
    pendencia_filtro = params['pendencia']
    search = params['search']
    quick = params['quick']

    if categoria:
        itens = itens.filter(categoria__icontains=categoria)

    if local_id:
        itens = itens.filter(local_aplicacao_id=local_id)

    if prioridade:
        itens = itens.filter(prioridade=prioridade)

    if search:
        busca_q = (
            Q(insumo__descricao__icontains=search)
            | Q(insumo__codigo_sienge__icontains=search)
            | Q(descricao_override__icontains=search)
            | Q(local_aplicacao__nome__icontains=search)
            | Q(responsavel__icontains=search)
        )
        if not mapa_suprimentos_manual():
            busca_q |= (
                Q(numero_sc__icontains=search)
                | Q(numero_pc__icontains=search)
                | Q(empresa_fornecedora__icontains=search)
            )
        itens = itens.filter(busca_q)

    if pendencia_filtro == 'SEM_LOCAL':
        itens = itens.filter(local_aplicacao__isnull=True)
    elif pendencia_filtro == 'SEM_PRAZO':
        itens = itens.filter(prazo_necessidade__isnull=True)
    elif pendencia_filtro == 'SEM_CODIGO':
        itens = itens.filter(
            Q(insumo__codigo_sienge='') | Q(insumo__codigo_sienge__startswith='SM-LEV-')
        )
    elif pendencia_filtro == 'INCOMPLETO':
        itens = itens.filter(
            Q(local_aplicacao__isnull=True)
            | Q(prazo_necessidade__isnull=True)
            | Q(insumo__codigo_sienge='')
            | Q(insumo__codigo_sienge__startswith='SM-LEV-')
            | Q(categoria='A CLASSIFICAR')
        )

    if quick == 'MEUS_ITENS' and request.user.is_authenticated:
        user = request.user
        nome = (user.get_full_name() or '').strip()
        username = (user.username or '').strip()
        meus_q = Q()
        if nome:
            meus_q |= Q(responsavel__icontains=nome)
        if username:
            meus_q |= Q(responsavel__icontains=username)
        if meus_q:
            itens = itens.filter(meus_q)
        else:
            itens = itens.none()

    if quick == 'PRAZO_7_DIAS':
        hoje = timezone.now().date()
        limite = hoje + timedelta(days=7)
        itens = itens.filter(
            prazo_necessidade__gte=hoje,
            prazo_necessidade__lte=limite,
        )

    if status_filtro:
        if manual:
            from suprimentos.views_engenharia import _mapa_filtrar_status_manual

            itens = _mapa_filtrar_status_manual(itens, status_filtro)
        else:
            from suprimentos.views_engenharia import (
                _attach_recebimentos_obra_cache,
                _mapa_itens_queryset,
            )

            itens_lista = list(itens)
            _oid_rec = int(obra_id) if obra_id else None
            _attach_recebimentos_obra_cache(itens_lista, _oid_rec)

            if status_filtro == 'LEVANTAMENTO':
                itens_lista = [
                    item for item in itens_lista
                    if not item.numero_sc or item.numero_sc.strip() == ''
                ]
            elif status_filtro == 'AGUARDANDO_COMPRA':
                itens_lista = [
                    item for item in itens_lista
                    if item.numero_sc and item.numero_sc.strip() != ''
                    and (not item.numero_pc or item.numero_pc.strip() == '')
                ]
            elif status_filtro == 'AGUARDANDO_ENTREGA':
                itens_lista = [
                    item for item in itens_lista
                    if item.numero_pc and item.numero_pc.strip() != ''
                    and item.quantidade_recebida_obra < item.quantidade_solicitada_sienge
                ]
            elif status_filtro == 'AGUARDANDO_ALOCACAO':
                itens_lista = [
                    item for item in itens_lista
                    if item.quantidade_recebida_obra > 0
                    and item.quantidade_alocada_local == 0
                ]
            elif status_filtro == 'PARCIAL':
                itens_lista = [
                    item for item in itens_lista
                    if item.quantidade_alocada_local > 0
                    and (
                        (
                            item.quantidade_solicitada_sienge > 0
                            and item.quantidade_alocada_local < item.quantidade_solicitada_sienge
                        )
                        or (
                            item.quantidade_solicitada_sienge == 0
                            and item.quantidade_planejada > 0
                            and item.quantidade_alocada_local < item.quantidade_planejada
                        )
                    )
                ]
            elif status_filtro == 'ENTREGUE':
                itens_lista = [
                    item for item in itens_lista
                    if (
                        (
                            item.quantidade_solicitada_sienge > 0
                            and item.quantidade_alocada_local >= item.quantidade_solicitada_sienge
                        )
                        or (
                            item.quantidade_solicitada_sienge == 0
                            and item.quantidade_planejada > 0
                            and item.quantidade_alocada_local >= item.quantidade_planejada
                        )
                    )
                ]
            elif status_filtro == 'ATRASADO':
                hoje = timezone.now().date()
                itens_lista = [
                    item for item in itens_lista
                    if item.prazo_necessidade
                    and item.prazo_necessidade < hoje
                    and (
                        (
                            item.quantidade_solicitada_sienge > 0
                            and item.quantidade_alocada_local < item.quantidade_solicitada_sienge
                        )
                        or (
                            item.quantidade_solicitada_sienge == 0
                            and item.quantidade_planejada > 0
                            and item.quantidade_alocada_local < item.quantidade_planejada
                        )
                    )
                ]

            if itens_lista:
                ids_filtrados = [item.id for item in itens_lista]
                itens = _mapa_itens_queryset(obra_id, prefetch_alocacoes=True).filter(
                    id__in=ids_filtrados
                )
            else:
                itens = ItemMapa.objects.none()

    return itens
