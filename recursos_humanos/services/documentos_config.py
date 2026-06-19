"""Montagem e persistência da configuração de documentos (visão por cargo/obra)."""
from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Count, Prefetch

from recursos_humanos.models import CargoRH, ObraLocal, TipoDocumento
from recursos_humanos.services.admissao_actions import sincronizar_documentos_em_andamento


@dataclass(frozen=True)
class DocCard:
    pk: int
    nome: str
    obrigatorio: bool
    tem_validade: bool
    dias_validade: int | None
    aplica_a: str
    aplica_label: str
    categoria: str
    categoria_label: str
    instrucoes_portal: str
    ativo: bool
    ordem: int
    cargos: list[str]
    cargo_ids: list[int]
    obras: list[str]


@dataclass(frozen=True)
class CargoResumo:
    pk: int
    nome: str
    docs_extras: int
    colaboradores: int


@dataclass(frozen=True)
class ObraResumo:
    pk: int
    nome: str
    docs_extras: int


@dataclass(frozen=True)
class KitPreviewItem:
    nome: str
    origem: str
    obrigatorio: bool
    tem_validade: bool
    dias_validade: int | None


def _tipo_para_card(tipo: TipoDocumento) -> DocCard:
    return DocCard(
        pk=tipo.pk,
        nome=tipo.nome,
        obrigatorio=tipo.obrigatorio,
        tem_validade=tipo.tem_validade,
        dias_validade=tipo.dias_validade,
        aplica_a=tipo.aplica_a,
        aplica_label=tipo.get_aplica_a_display(),
        categoria=tipo.categoria,
        categoria_label=tipo.get_categoria_display(),
        instrucoes_portal=tipo.instrucoes_portal or '',
        ativo=tipo.ativo,
        ordem=tipo.ordem,
        cargos=[c.nome for c in tipo.cargos_aplicaveis.all()],
        cargo_ids=[c.pk for c in tipo.cargos_aplicaveis.all()],
        obras=[o.nome for o in tipo.obras_aplicaveis.all()],
    )


def carregar_tipos_documento() -> list[TipoDocumento]:
    return list(
        TipoDocumento.objects.prefetch_related('cargos_aplicaveis', 'obras_aplicaveis')
        .order_by('ordem', 'nome')
    )


def montar_cards_tipos(tipos: list[TipoDocumento] | None = None) -> dict[str, list[DocCard]]:
    lista = tipos if tipos is not None else carregar_tipos_documento()
    return {
        'todos': [_tipo_para_card(t) for t in lista if t.aplica_a == TipoDocumento.AplicaA.TODOS],
        'por_cargo': [_tipo_para_card(t) for t in lista if t.aplica_a == TipoDocumento.AplicaA.POR_CARGO],
        'por_obra': [_tipo_para_card(t) for t in lista if t.aplica_a == TipoDocumento.AplicaA.POR_OBRA],
    }


def montar_catalogo_documentos(cards: dict[str, list[DocCard]] | None = None) -> list[DocCard]:
    """Lista unificada do catálogo para gestão (editar/excluir)."""
    if cards is None:
        cards = montar_cards_tipos()
    lista = list(cards.get('todos', [])) + list(cards.get('por_cargo', []))
    return sorted(lista, key=lambda d: (d.ordem, d.nome.lower()))


def montar_cargos_resumo(tipos_por_cargo: list[DocCard] | None = None) -> list[CargoResumo]:
    if tipos_por_cargo is None:
        tipos_por_cargo = montar_cards_tipos()['por_cargo']
    cargos = (
        CargoRH.objects.annotate(colaboradores_count=Count('colaboradores', distinct=True))
        .order_by('nome')
    )
    resultado: list[CargoResumo] = []
    for cargo in cargos:
        extras = sum(1 for doc in tipos_por_cargo if cargo.nome in doc.cargos)
        resultado.append(
            CargoResumo(
                pk=cargo.pk,
                nome=cargo.nome,
                docs_extras=extras,
                colaboradores=cargo.colaboradores_count,
            )
        )
    return resultado


def montar_obras_resumo(tipos_por_obra: list[DocCard] | None = None) -> list[ObraResumo]:
    if tipos_por_obra is None:
        tipos_por_obra = montar_cards_tipos()['por_obra']
    obras = ObraLocal.objects.order_by('nome')
    return [
        ObraResumo(
            pk=obra.pk,
            nome=obra.nome,
            docs_extras=sum(1 for doc in tipos_por_obra if obra.nome in doc.obras),
        )
        for obra in obras
    ]


def ids_docs_do_cargo(cargo: CargoRH, tipos: list[TipoDocumento] | None = None) -> set[int]:
    lista = tipos if tipos is not None else carregar_tipos_documento()
    return {
        t.pk for t in lista
        if t.aplica_a == TipoDocumento.AplicaA.POR_CARGO
        and t.cargos_aplicaveis.filter(pk=cargo.pk).exists()
    }


def ids_docs_da_obra(obra: ObraLocal, tipos: list[TipoDocumento] | None = None) -> set[int]:
    lista = tipos if tipos is not None else carregar_tipos_documento()
    return {
        t.pk for t in lista
        if t.aplica_a == TipoDocumento.AplicaA.POR_OBRA
        and t.obras_aplicaveis.filter(pk=obra.pk).exists()
    }


def salvar_docs_do_cargo(cargo_id: int, tipo_ids: list[int]) -> int:
    cargo = CargoRH.objects.get(pk=cargo_id)
    selecionados = {int(x) for x in tipo_ids}
    for tipo in TipoDocumento.objects.filter(aplica_a=TipoDocumento.AplicaA.POR_CARGO):
        if tipo.pk in selecionados:
            tipo.cargos_aplicaveis.add(cargo)
        else:
            tipo.cargos_aplicaveis.remove(cargo)
    return sincronizar_documentos_em_andamento()


def salvar_docs_da_obra(obra_id: int, tipo_ids: list[int]) -> int:
    obra = ObraLocal.objects.get(pk=obra_id)
    selecionados = {int(x) for x in tipo_ids}
    for tipo in TipoDocumento.objects.filter(aplica_a=TipoDocumento.AplicaA.POR_OBRA):
        if tipo.pk in selecionados:
            tipo.obras_aplicaveis.add(obra)
        else:
            tipo.obras_aplicaveis.remove(obra)
    return sincronizar_documentos_em_andamento()


def preview_kit_documentos(
    *,
    cargo_id: int | None = None,
    obra_id: int | None = None,
) -> dict:
    """Simula o pacote documental para cargo + obra opcional."""
    tipos = carregar_tipos_documento()
    cargo_nome = None
    obra_nome = None
    if cargo_id:
        cargo = CargoRH.objects.filter(pk=cargo_id).first()
        if cargo:
            cargo_nome = cargo.nome
        else:
            cargo_id = None
    if obra_id:
        obra = ObraLocal.objects.filter(pk=obra_id).first()
        if obra:
            obra_nome = obra.nome
        else:
            obra_id = None

    itens: list[KitPreviewItem] = []
    for tipo in tipos:
        if not tipo.ativo:
            continue
        if tipo.aplica_a == TipoDocumento.AplicaA.TODOS:
            incluir = True
            origem = 'Todos'
        elif tipo.aplica_a == TipoDocumento.AplicaA.POR_CARGO:
            incluir = bool(
                cargo_id and tipo.cargos_aplicaveis.filter(pk=cargo_id).exists()
            )
            origem = 'Cargo'
        elif tipo.aplica_a == TipoDocumento.AplicaA.POR_OBRA:
            incluir = bool(
                obra_id and tipo.obras_aplicaveis.filter(pk=obra_id).exists()
            )
            origem = 'Obra'
        else:
            incluir = False
        if not incluir:
            continue
        itens.append(
            KitPreviewItem(
                nome=tipo.nome,
                origem=origem,
                obrigatorio=tipo.obrigatorio,
                tem_validade=tipo.tem_validade,
                dias_validade=tipo.dias_validade,
            )
        )

    return {
        'total': len(itens),
        'obrigatorios': sum(1 for i in itens if i.obrigatorio),
        'com_validade': sum(1 for i in itens if i.tem_validade),
        'itens': [
            {
                'nome': i.nome,
                'origem': i.origem,
                'obrigatorio': i.obrigatorio,
                'tem_validade': i.tem_validade,
                'dias_validade': i.dias_validade,
            }
            for i in itens
        ],
        'cargo_id': cargo_id,
        'cargo_nome': cargo_nome,
        'obra_id': obra_id,
        'obra_nome': obra_nome,
    }


def garantir_cargos_rh_padrao() -> int:
    """Sincroniza cargos RH a partir do catálogo quando a lista está vazia."""
    if CargoRH.objects.exists():
        return 0
    from recursos_humanos.models import CargoCatalogo

    criados = 0
    for nome in CargoCatalogo.objects.values_list('nome', flat=True).order_by('nome')[:12]:
        _, created = CargoRH.objects.get_or_create(nome=nome)
        if created:
            criados += 1
    if criados:
        return criados
    for nome in ('Pedreiro', 'Servente', 'Mestre de Obras', 'Encarregado de Obras', 'Auxiliar Administrativa'):
        _, created = CargoRH.objects.get_or_create(nome=nome)
        if created:
            criados += 1
    return criados
