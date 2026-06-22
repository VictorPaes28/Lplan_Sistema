"""Filtros da lista lateral do fluxo de admissão."""
from __future__ import annotations

from django.db.models import Q, QuerySet

from recursos_humanos.models import Colaborador
from recursos_humanos.services.admissao_actions import (
    _usuario_pode_aprovar_requisicao,
    colaborador_admissao_concluida,
)

FILTRO_TODAS = 'todas'
FILTRO_MINHA_APROVACAO = 'minha_aprovacao'
FILTRO_EM_ANDAMENTO = 'em_andamento'
FILTRO_PENDENCIAS = 'pendencias'
FILTRO_REPROVADAS = 'reprovadas'
FILTRO_CONCLUIDAS = 'concluidas'
FILTRO_MINHAS = 'minhas'
FILTRO_ETAPA_1 = 'etapa_1'
FILTRO_ETAPA_2 = 'etapa_2'
FILTRO_ETAPA_3 = 'etapa_3'
FILTRO_ETAPA_4 = 'etapa_4'
FILTRO_ETAPA_5 = 'etapa_5'

FILTROS_FLUXO_ADMISSAO: tuple[tuple[str, str], ...] = (
    (FILTRO_MINHA_APROVACAO, 'Minha aprovação'),
    (FILTRO_EM_ANDAMENTO, 'Em andamento'),
    (FILTRO_PENDENCIAS, 'Com pendências'),
    (FILTRO_REPROVADAS, 'Reprovadas'),
    (FILTRO_CONCLUIDAS, 'Concluídas'),
    (FILTRO_MINHAS, 'Criadas por mim'),
    (FILTRO_ETAPA_1, 'Etapa 1'),
    (FILTRO_ETAPA_2, 'Etapa 2'),
    (FILTRO_ETAPA_3, 'Etapa 3'),
    (FILTRO_ETAPA_4, 'Etapa 4'),
    (FILTRO_ETAPA_5, 'Etapa 5'),
    (FILTRO_TODAS, 'Todas'),
)

FILTROS_VALIDOS = frozenset(chave for chave, _ in FILTROS_FLUXO_ADMISSAO)

_ETAPA_POR_FILTRO = {
    FILTRO_ETAPA_1: 1,
    FILTRO_ETAPA_2: 2,
    FILTRO_ETAPA_3: 3,
    FILTRO_ETAPA_4: 4,
    FILTRO_ETAPA_5: 5,
}

_ROTULO_CURTO_ETAPA = {
    1: 'Requisição',
    2: 'Docs',
    3: 'Validação',
    4: 'Contrato',
    5: 'Ativo',
}


def _rotulo_curto_etapa(num: int, nome: str) -> str:
    return _ROTULO_CURTO_ETAPA.get(num) or (nome[:10] + '…' if len(nome) > 10 else nome)


def _requisicao_pendente_aprovacao(colaborador: Colaborador) -> bool:
    return (
        colaborador.etapa_admissao == 1
        and not colaborador.requisicao_aprovada_gestor
        and not colaborador.requisicao_reprovada
    )


def _pendente_minha_aprovacao(colaborador: Colaborador, user) -> bool:
    return _requisicao_pendente_aprovacao(colaborador) and _usuario_pode_aprovar_requisicao(
        colaborador, user,
    )


def _tem_pendencia_fluxo(colaborador: Colaborador) -> bool:
    from recursos_humanos.services.documentos import colaborador_tem_pendencia_documentos

    if colaborador.status != Colaborador.Status.EM_ADMISSAO:
        return False
    if _requisicao_pendente_aprovacao(colaborador):
        return True
    if colaborador.requisicao_reprovada:
        return True
    return colaborador_tem_pendencia_documentos(colaborador)


def _criadas_por_mim(colaborador: Colaborador, user) -> bool:
    from recursos_humanos.services.admissao_actions import _usuario_e_criador_requisicao

    return _usuario_e_criador_requisicao(colaborador, user)


def aplicar_filtro_fluxo_admissao(
    qs: QuerySet,
    filtro: str,
    user,
) -> QuerySet:
    if not filtro or filtro == FILTRO_TODAS:
        return qs

    if filtro == FILTRO_MINHA_APROVACAO:
        return qs.filter(
            etapa_admissao=1,
            requisicao_aprovada_gestor=False,
            requisicao_reprovada=False,
        ).filter(
            Q(gestor_aprovador_user=user) | Q(aprovadores_requisicao=user),
        ).distinct()

    if filtro == FILTRO_EM_ANDAMENTO:
        return qs.filter(status=Colaborador.Status.EM_ADMISSAO)

    if filtro == FILTRO_REPROVADAS:
        return qs.filter(
            etapa_admissao=1,
            requisicao_reprovada=True,
        )

    if filtro == FILTRO_MINHAS:
        if not user or not user.is_authenticated:
            return qs.none()
        ids = [c.pk for c in list(qs) if _criadas_por_mim(c, user)]
        return qs.filter(pk__in=ids)

    if filtro in _ETAPA_POR_FILTRO:
        return qs.filter(etapa_admissao=_ETAPA_POR_FILTRO[filtro])

    if filtro in (FILTRO_PENDENCIAS, FILTRO_CONCLUIDAS):
        ids = []
        for colaborador in list(qs):
            if filtro == FILTRO_PENDENCIAS and _tem_pendencia_fluxo(colaborador):
                ids.append(colaborador.pk)
            elif filtro == FILTRO_CONCLUIDAS and colaborador_admissao_concluida(colaborador):
                ids.append(colaborador.pk)
        return qs.filter(pk__in=ids)

    return qs


def contar_filtros_fluxo_admissao(qs: QuerySet, user) -> dict[str, int]:
    contagens = {chave: 0 for chave, _ in FILTROS_FLUXO_ADMISSAO}
    lista = list(qs)
    contagens[FILTRO_TODAS] = len(lista)

    for colaborador in lista:
        if colaborador.status == Colaborador.Status.EM_ADMISSAO:
            contagens[FILTRO_EM_ANDAMENTO] += 1
        if _tem_pendencia_fluxo(colaborador):
            contagens[FILTRO_PENDENCIAS] += 1
        if colaborador.requisicao_reprovada and colaborador.etapa_admissao == 1:
            contagens[FILTRO_REPROVADAS] += 1
        if colaborador_admissao_concluida(colaborador):
            contagens[FILTRO_CONCLUIDAS] += 1
        if user and user.is_authenticated and _criadas_por_mim(colaborador, user):
            contagens[FILTRO_MINHAS] += 1
        if user and user.is_authenticated and _pendente_minha_aprovacao(colaborador, user):
            contagens[FILTRO_MINHA_APROVACAO] += 1
        for chave, etapa in _ETAPA_POR_FILTRO.items():
            if colaborador.etapa_admissao == etapa:
                contagens[chave] += 1

    return contagens


def filtro_padrao_fluxo_admissao(qs: QuerySet, user) -> str:
    contagens = contar_filtros_fluxo_admissao(qs, user)
    if contagens.get(FILTRO_MINHA_APROVACAO, 0) > 0:
        return FILTRO_MINHA_APROVACAO
    if contagens.get(FILTRO_EM_ANDAMENTO, 0) > 0:
        return FILTRO_EM_ANDAMENTO
    return FILTRO_TODAS


def resolver_filtro_fluxo_admissao(filtro_param: str | None, qs: QuerySet, user) -> str:
    filtro = (filtro_param or '').strip()
    if filtro in FILTROS_VALIDOS:
        return filtro
    return filtro_padrao_fluxo_admissao(qs, user)


def _item_filtro_ui(
    chave: str,
    rotulo: str,
    contagens: dict[str, int],
    filtro_ativo: str,
    *,
    icone: str = '',
    destaque: bool = False,
    tom: str = '',
    titulo: str = '',
    subtitulo: str = '',
) -> dict:
    count = contagens.get(chave, 0)
    return {
        'chave': chave,
        'rotulo': rotulo,
        'subtitulo': subtitulo,
        'count': count,
        'ativo': filtro_ativo == chave,
        'destaque': destaque and count > 0 and filtro_ativo != chave,
        'tom': tom,
        'icone': icone,
        'titulo': titulo or rotulo,
        'vazio': count == 0,
    }


def montar_ui_grupos_filtro_fluxo(
    contagens: dict[str, int],
    filtro_ativo: str,
    etapas_labels: list[tuple[int, str]] | None = None,
) -> list[dict]:
    """Agrupa filtros para painel lateral legível (listas + etapas compactas)."""
    etapa_nomes = dict(etapas_labels or [])

    def item(chave, rotulo, **kwargs):
        return _item_filtro_ui(chave, rotulo, contagens, filtro_ativo, **kwargs)

    etapas_itens = []
    for num in range(1, 6):
        chave = f'etapa_{num}'
        nome = etapa_nomes.get(num, f'Etapa {num}')
        etapas_itens.append(item(
            chave,
            str(num),
            titulo=f'Etapa {num} — {nome}',
            subtitulo=_rotulo_curto_etapa(num, nome),
        ))

    return [
        {
            'id': 'rapida',
            'titulo': 'Visão rápida',
            'layout': 'lista',
            'itens': [
                item(
                    FILTRO_MINHA_APROVACAO,
                    'Minha aprovação',
                    icone='fa-stamp',
                    destaque=True,
                    tom='amber',
                ),
                item(FILTRO_EM_ANDAMENTO, 'Em andamento', icone='fa-route'),
                item(
                    FILTRO_PENDENCIAS,
                    'Pendências',
                    icone='fa-exclamation-circle',
                    tom='amber',
                ),
            ],
        },
        {
            'id': 'situacao',
            'titulo': 'Situação',
            'layout': 'lista',
            'itens': [
                item(FILTRO_REPROVADAS, 'Reprovadas', icone='fa-times-circle', tom='red'),
                item(FILTRO_CONCLUIDAS, 'Concluídas', icone='fa-check-circle', tom='green'),
                item(FILTRO_MINHAS, 'Minhas requisições', icone='fa-user-edit'),
            ],
        },
        {
            'id': 'etapas',
            'titulo': 'Por etapa',
            'layout': 'etapas',
            'itens': etapas_itens,
        },
    ]


def rotulo_filtro_fluxo_ativo(filtro: str, etapas_labels: list[tuple[int, str]] | None = None) -> str:
    for chave, rotulo in FILTROS_FLUXO_ADMISSAO:
        if chave == filtro:
            return rotulo
    if filtro.startswith('etapa_'):
        try:
            num = int(filtro.split('_', 1)[1])
        except (IndexError, ValueError):
            return filtro
        nomes = dict(etapas_labels or [])
        return f'Etapa {num} — {nomes.get(num, "")}'.strip(' —')
    return 'Todas'
