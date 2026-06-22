"""Dados operacionais para a lista de colaboradores (pendências e resumo de docs)."""
from __future__ import annotations

import re

from dataclasses import dataclass

from django.urls import reverse
from django.utils import timezone

from recursos_humanos.models import Colaborador, DocumentoColaborador, PrazoContrato
from recursos_humanos.services.alertas_config import obter_configuracao_alertas
from recursos_humanos.services.alerts import _doc_deve_gerar_alerta, _urgencia_por_dias
from recursos_humanos.services.documentos import (
    documento_conta_como_recebido,
    documento_precisa_atencao,
)
from recursos_humanos.services.papeis_fluxo import ETAPAS_FLUXO_LABELS
from recursos_humanos.services.prazo_contrato import NOME_EXPERIENCIA_CLT

_MAX_PENDENCIAS_VISIVEIS = 2

_ETAPA_LABEL = dict(ETAPAS_FLUXO_LABELS)

_PRAZO_CURTO = {
    PrazoContrato.Tipo.EXPERIENCIA: NOME_EXPERIENCIA_CLT,
    PrazoContrato.Tipo.DETERMINADO: 'Determinado',
    PrazoContrato.Tipo.ESTAGIO: 'Estágio',
    PrazoContrato.Tipo.PJ: 'PJ',
}


@dataclass(frozen=True)
class ResumoContratoLista:
    progresso: str
    tipo_curto: str
    hint: str
    pct: int
    tom: str


@dataclass(frozen=True)
class PendenciaListaItem:
    label: str
    hint: str
    urgencia: str
    ordem: int


@dataclass(frozen=True)
class ResumoDocumentosLista:
    recebidos: int
    total: int
    pendentes_count: int
    completo: bool
    fracao: str


def _nome_curto(nome: str, *, max_len: int = 16) -> str:
    for sep in (' – ', ' - ', ' — ', ':'):
        if sep in nome:
            parte = nome.split(sep, 1)[0].strip()
            if parte:
                return parte
    nome = re.sub(r'\s+', ' ', nome).strip()
    if len(nome) <= max_len:
        return nome
    return nome[: max_len - 1].rstrip() + '…'


def _prazo_curto(prazo: PrazoContrato) -> str:
    return _PRAZO_CURTO.get(prazo.tipo, _nome_curto(prazo.get_tipo_display(), max_len=12))


def _tom_progresso_prazo(*, urgencia: str | None = None, dias_restantes: int | None = None) -> str:
    if urgencia in ('red', 'critico', 'urgente'):
        return 'bad'
    if urgencia in ('yellow', 'atencao'):
        return 'warn'
    if dias_restantes is not None:
        if dias_restantes < 0:
            return 'bad'
        if dias_restantes <= 7:
            return 'bad'
        if dias_restantes <= 30:
            return 'warn'
    return 'ok'


def obter_resumo_contrato_lista(colaborador: Colaborador) -> ResumoContratoLista | None:
    """Progresso compacto do contrato ativo para a coluna da lista (ex.: 42/45, 75/200)."""
    if colaborador.status != Colaborador.Status.ATIVO:
        return None

    from recursos_humanos.services.prazo_contrato import (
        calcular_situacao_experiencia,
        colaborador_recebe_prazo_teste_clt,
        formatar_progresso_prazo_ativo,
        formatar_progresso_prazo_teste_clt,
        pct_progresso_texto,
        prazo_teste_clt_deve_exibir,
        prioridade_experiencia_para_urgencia,
    )

    if colaborador_recebe_prazo_teste_clt(colaborador):
        situacao = calcular_situacao_experiencia(colaborador)
        if situacao and prazo_teste_clt_deve_exibir(situacao):
            progresso = formatar_progresso_prazo_teste_clt(situacao)
            urgencia = prioridade_experiencia_para_urgencia(situacao.prioridade)
            tom_map = {'green': 'ok', 'yellow': 'warn', 'red': 'bad'}
            return ResumoContratoLista(
                progresso=progresso,
                tipo_curto='Período',
                hint=(
                    f'{NOME_EXPERIENCIA_CLT} · admissão {situacao.data_admissao:%d/%m/%Y} · '
                    f'marco D{situacao.proximo_marco} ({situacao.proximo_marco_data:%d/%m/%Y})'
                ),
                pct=pct_progresso_texto(progresso),
                tom=tom_map.get(urgencia, 'ok'),
            )

    prazos = getattr(colaborador, '_prefetched_objects_cache', {}).get('prazos_contrato')
    if prazos is None:
        prazos = colaborador.prazos_contrato.filter(status=PrazoContrato.Status.ATIVO)
    else:
        prazos = [p for p in prazos if p.status == PrazoContrato.Status.ATIVO]

    candidatos = []
    for prazo in prazos:
        if prazo.tipo == PrazoContrato.Tipo.EXPERIENCIA:
            continue
        progresso = formatar_progresso_prazo_ativo(prazo)
        if not progresso:
            continue
        dias = prazo.dias_restantes()
        candidatos.append((prazo, progresso, dias if dias is not None else 9999))

    if not candidatos:
        return None

    prazo, progresso, dias = min(candidatos, key=lambda item: item[2])
    tipo = _prazo_curto(prazo)
    fim_txt = prazo.data_fim.strftime('%d/%m/%Y') if prazo.data_fim else '—'
    hint = f'{prazo.get_tipo_display()} · {prazo.data_inicio:%d/%m/%Y} a {fim_txt}'
    if dias < 0:
        hint += f' · vencido há {abs(dias)} dia(s)'
    elif dias == 0:
        hint += ' · vence hoje'
    else:
        hint += f' · {dias} dia(s) restantes'

    return ResumoContratoLista(
        progresso=progresso,
        tipo_curto=tipo,
        hint=hint,
        pct=pct_progresso_texto(progresso),
        tom=_tom_progresso_prazo(dias_restantes=dias),
    )


def _score_urgencia(urgencia: str, dias: int | None) -> int:
    base = {'red': 0, 'yellow': 100, 'neutral': 200}.get(urgencia, 300)
    if dias is None:
        return base + 500
    return base + max(dias, -999)


def _pendencias_documentos_validade(
    colaborador: Colaborador,
    docs: list[DocumentoColaborador],
    hoje,
    config,
) -> list[PendenciaListaItem]:
    itens: list[PendenciaListaItem] = []
    for doc in docs:
        if doc.vencimento is None or not doc.tipo.tem_validade:
            continue
        dias = (doc.vencimento - hoje).days
        if not _doc_deve_gerar_alerta(doc, hoje, dias, config):
            continue
        nome = _nome_curto(doc.tipo.nome)
        if dias < 0:
            label = f'{nome} · vencido'
            hint = f'{doc.tipo.nome} — venceu em {doc.vencimento:%d/%m/%Y}'
            urgencia = 'red'
        elif dias == 0:
            label = f'{nome} · hoje'
            hint = f'{doc.tipo.nome} — vence hoje'
            urgencia = 'red'
        else:
            label = f'{nome} · {dias}d'
            hint = f'{doc.tipo.nome} — vence em {doc.vencimento:%d/%m/%Y}'
            urgencia = _urgencia_por_dias(dias)
        itens.append(
            PendenciaListaItem(label, hint, urgencia, _score_urgencia(urgencia, dias))
        )
    return itens


def _pendencias_prazo_contrato(
    colaborador: Colaborador,
    config,
) -> list[PendenciaListaItem]:
    if colaborador.status == Colaborador.Status.DESLIGADO:
        return []
    from recursos_humanos.services.prazo_contrato import (
        calcular_situacao_experiencia,
        colaborador_recebe_prazo_teste_clt,
        formatar_progresso_prazo_teste_clt,
        prazo_teste_clt_deve_exibir,
        prioridade_experiencia_para_urgencia,
    )

    hoje = timezone.localdate()
    limite = hoje.toordinal() + config.dias_antecedencia_documentos
    itens: list[PendenciaListaItem] = []

    if colaborador_recebe_prazo_teste_clt(colaborador):
        situacao = calcular_situacao_experiencia(colaborador)
        if situacao and prazo_teste_clt_deve_exibir(situacao):
            dias = situacao.dias_restantes_marco
            urgencia = prioridade_experiencia_para_urgencia(situacao.prioridade)
            if dias < 0:
                label = f'{NOME_EXPERIENCIA_CLT} · marco vencido'
                hint = (
                    f'Marco D{situacao.proximo_marco} — '
                    f'admissão {situacao.data_admissao:%d/%m/%Y}'
                )
            elif dias == 0:
                label = f'{NOME_EXPERIENCIA_CLT} · marco hoje'
                hint = f'Marco D{situacao.proximo_marco} vence hoje'
            else:
                label = f'{NOME_EXPERIENCIA_CLT} · marco {dias}d'
                hint = (
                    f'Marco D{situacao.proximo_marco} em '
                    f'{situacao.proximo_marco_data:%d/%m/%Y}'
                )
            itens.append(
                PendenciaListaItem(label, hint, urgencia, _score_urgencia(urgencia, dias))
            )

    prazos = getattr(colaborador, '_prefetched_objects_cache', {}).get('prazos_contrato')
    if prazos is None:
        prazos = colaborador.prazos_contrato.all()
    for prazo in prazos:
        if prazo.status != PrazoContrato.Status.ATIVO or prazo.data_fim is None:
            continue
        if prazo.tipo == PrazoContrato.Tipo.EXPERIENCIA:
            continue

        if prazo.data_fim.toordinal() > limite:
            continue
        dias = prazo.dias_restantes()
        if dias is None:
            continue
        tipo = _prazo_curto(prazo)
        if dias < 0:
            label = f'{tipo} · vencido'
            hint = f'{prazo.get_tipo_display()} — venceu em {prazo.data_fim:%d/%m/%Y}'
            urgencia = 'red'
        elif dias == 0:
            label = f'{tipo} · hoje'
            hint = f'{prazo.get_tipo_display()} — vence hoje'
            urgencia = 'red'
        else:
            label = f'{tipo} · {dias}d'
            hint = f'{prazo.get_tipo_display()} — {prazo.data_fim:%d/%m/%Y}'
            urgencia = _urgencia_por_dias(dias)
        itens.append(
            PendenciaListaItem(label, hint, urgencia, _score_urgencia(urgencia, dias))
        )
    return itens


def _pendencias_dossie_ativo(
    colaborador: Colaborador,
    docs: list[DocumentoColaborador],
) -> list[PendenciaListaItem]:
    """Pendências documentais do quadro (vínculo já ativo)."""
    if colaborador.status != Colaborador.Status.ATIVO:
        return []
    pendentes = [doc for doc in docs if documento_precisa_atencao(doc, colaborador)]
    faltando = sum(1 for doc in pendentes if doc.status == DocumentoColaborador.Status.FALTANDO)
    aguardando = sum(
        1 for doc in pendentes
        if doc.status in (
            DocumentoColaborador.Status.PENDENTE,
            DocumentoColaborador.Status.FALTANDO,
        )
    )
    itens: list[PendenciaListaItem] = []
    if faltando:
        itens.append(
            PendenciaListaItem(
                label=f'Dossiê · {faltando} falta{"m" if faltando != 1 else ""}',
                hint='Documentos do quadro ainda não recebidos',
                urgencia='red',
                ordem=40,
            )
        )
    elif aguardando and not faltando:
        itens.append(
            PendenciaListaItem(
                label='Dossiê · conferir',
                hint='Documentos aguardando conferência ou reenvio',
                urgencia='yellow',
                ordem=55,
            )
        )
    return itens


def _pendencias_admissao(
    colaborador: Colaborador,
    docs: list[DocumentoColaborador],
) -> list[PendenciaListaItem]:
    """Somente alertas acionáveis — etapa e docs ficam em Situação/Documentos."""
    if colaborador.status != Colaborador.Status.EM_ADMISSAO:
        return []
    itens: list[PendenciaListaItem] = []
    etapa = colaborador.etapa_admissao or 1

    if colaborador.requisicao_reprovada:
        itens.append(
            PendenciaListaItem(
                label='Requisição',
                hint='Requisição reprovada — corrigir e reenviar',
                urgencia='red',
                ordem=10,
            )
        )
    elif etapa == 1 and not colaborador.requisicao_aprovada_gestor:
        itens.append(
            PendenciaListaItem(
                label='Requisição',
                hint='Registro legado aguardando aprovação manual',
                urgencia='yellow',
                ordem=80,
            )
        )

    pendentes = [doc for doc in docs if documento_precisa_atencao(doc, colaborador)]
    faltando = sum(1 for doc in pendentes if doc.status == DocumentoColaborador.Status.FALTANDO)
    if faltando:
        itens.append(
            PendenciaListaItem(
                label=f'{faltando} falta{"m" if faltando != 1 else ""}',
                hint='Documentos ainda não enviados pelo candidato',
                urgencia='red',
                ordem=35,
            )
        )
    return itens


def listar_pendencias_colaborador(
    colaborador: Colaborador,
    *,
    docs: list[DocumentoColaborador] | None = None,
    config=None,
) -> list[PendenciaListaItem]:
    hoje = timezone.localdate()
    cfg = config or obter_configuracao_alertas()
    doc_list = docs if docs is not None else list(colaborador.documentos.select_related('tipo'))

    itens: list[PendenciaListaItem] = []
    itens.extend(_pendencias_admissao(colaborador, doc_list))
    itens.extend(_pendencias_dossie_ativo(colaborador, doc_list))
    itens.extend(_pendencias_documentos_validade(colaborador, doc_list, hoje, cfg))
    itens.extend(_pendencias_prazo_contrato(colaborador, cfg))

    itens.sort(key=lambda item: item.ordem)
    return itens


def resumo_documentos_lista(
    colaborador: Colaborador,
    *,
    docs: list[DocumentoColaborador] | None = None,
    recebidos: int | None = None,
    total: int | None = None,
) -> ResumoDocumentosLista:
    doc_list = docs if docs is not None else list(colaborador.documentos.select_related('tipo'))
    rec = recebidos if recebidos is not None else sum(
        1 for doc in doc_list if documento_conta_como_recebido(doc)
    )
    tot = total if total is not None else len(doc_list)
    pendentes = [doc for doc in doc_list if documento_precisa_atencao(doc, colaborador)]
    completo = tot > 0 and rec >= tot and not pendentes
    return ResumoDocumentosLista(
        recebidos=rec,
        total=tot,
        pendentes_count=len(pendentes),
        completo=completo,
        fracao=f'{rec}/{tot}' if tot else '0/0',
    )


def enriquecer_lista_colaborador(
    colaborador: Colaborador,
    *,
    docs: list[DocumentoColaborador] | None = None,
    recebidos: int | None = None,
    total: int | None = None,
) -> Colaborador:
    doc_list = docs
    if doc_list is None and hasattr(colaborador, '_prefetched_objects_cache'):
        doc_list = colaborador._prefetched_objects_cache.get('documentos')
    if doc_list is None:
        doc_list = list(colaborador.documentos.select_related('tipo'))

    pendencias = listar_pendencias_colaborador(colaborador, docs=doc_list)
    resumo_docs = resumo_documentos_lista(
        colaborador,
        docs=doc_list,
        recebidos=recebidos,
        total=total,
    )

    colaborador.pendencias_lista = pendencias
    colaborador.pendencias_visiveis = pendencias[:_MAX_PENDENCIAS_VISIVEIS]
    colaborador.pendencias_extra = max(0, len(pendencias) - _MAX_PENDENCIAS_VISIVEIS)
    colaborador.resumo_contrato = obter_resumo_contrato_lista(colaborador)
    colaborador.resumo_docs = resumo_docs

    etapa = colaborador.etapa_admissao or 1
    if colaborador.status == Colaborador.Status.EM_ADMISSAO:
        colaborador.etapa_badge = f'{etapa}/5'
        colaborador.etapa_nome_curto = _ETAPA_LABEL.get(etapa, f'Etapa {etapa}')
    else:
        colaborador.etapa_badge = ''
        colaborador.etapa_nome_curto = ''

    obras = list(colaborador.obras.all())
    colaborador.obras_visiveis = obras[:1]
    colaborador.obras_extra = max(0, len(obras) - 1)

    if colaborador.status == Colaborador.Status.EM_ADMISSAO:
        colaborador.url_operacional = (
            f"{reverse('recursos_humanos:admissao')}?id={colaborador.pk}"
        )
    else:
        colaborador.url_operacional = reverse(
            'recursos_humanos:colaboradores_list',
        ) + f'?abrir_colaborador={colaborador.pk}&abrir_colaborador_tab=documentos'

    return colaborador
