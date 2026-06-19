"""Rótulos de status contextualizados para listagem e perfil do colaborador."""
from __future__ import annotations

from dataclasses import dataclass

from recursos_humanos.models import Colaborador
from recursos_humanos.services.papeis_fluxo import ETAPAS_FLUXO_LABELS

_ETAPA_LABEL = dict(ETAPAS_FLUXO_LABELS)

_ADMISSAO_HINTS = {
    2: 'Coleta e conferência no portal',
    3: 'Pacote documental completo',
    4: 'PDF e assinatura ZapSign',
    5: 'Aguardando ativação',
}

_ADMISSAO_TONES = {
    1: 'adm-requisicao',
    2: 'adm-docs',
    3: 'adm-validacao',
    4: 'adm-contrato',
    5: 'adm-final',
}


@dataclass(frozen=True)
class StatusExibicao:
    label: str
    hint: str
    tone: str
    status: str


def status_exibicao_colaborador(
    colaborador: Colaborador,
    *,
    docs_recebidos: int | None = None,
    docs_total: int | None = None,
) -> StatusExibicao:
    status = colaborador.status
    if status == Colaborador.Status.EM_ADMISSAO:
        return _status_admissao(colaborador)
    if status == Colaborador.Status.ATIVO:
        return _status_ativo(colaborador, docs_recebidos, docs_total)
    return StatusExibicao(
        label='Desligado',
        hint='Vínculo encerrado',
        tone='desligado',
        status=status,
    )


def _status_admissao(colaborador: Colaborador) -> StatusExibicao:
    etapa = colaborador.etapa_admissao or 1
    if etapa == 1:
        if colaborador.requisicao_reprovada:
            return StatusExibicao(
                label='Correção de requisição',
                hint='Etapa 1/5 — requisição reprovada, aguardando correção',
                tone='adm-reprovada',
                status=colaborador.status,
            )
        if not colaborador.requisicao_aprovada_gestor:
            return StatusExibicao(
                label='Requisição pendente',
                hint='Etapa 1/5 — registro legado aguardando aprovação',
                tone='adm-requisicao',
                status=colaborador.status,
            )
    label = _ETAPA_LABEL.get(etapa, f'Etapa {etapa}')
    hint = _ADMISSAO_HINTS.get(etapa, f'Fluxo de admissão')
    hint = f'Etapa {etapa}/5 — {hint}'
    tone = _ADMISSAO_TONES.get(etapa, 'adm-docs')
    return StatusExibicao(label, hint, tone, colaborador.status)


def _status_ativo(
    colaborador: Colaborador,
    docs_recebidos: int | None,
    docs_total: int | None,
) -> StatusExibicao:
    recebidos = docs_recebidos if docs_recebidos is not None else colaborador.documentos_recebidos()
    total = docs_total if docs_total is not None else colaborador.documentos_total()
    if total and recebidos < total:
        faltam = total - recebidos
        return StatusExibicao(
            label='Em exercício',
            hint=(
                f'Dossiê {recebidos}/{total} — {faltam} pendente{"s" if faltam != 1 else ""} '
                '(conferir documentos ou validades)'
            ),
            tone='contratado-pendente',
            status=colaborador.status,
        )
    return StatusExibicao(
        label='Em exercício',
        hint='Vínculo ativo · dossiê completo',
        tone='contratado',
        status=colaborador.status,
    )


def aplicar_status_exibicao(
    colaborador: Colaborador,
    *,
    docs_recebidos: int | None = None,
    docs_total: int | None = None,
) -> Colaborador:
    ex = status_exibicao_colaborador(
        colaborador,
        docs_recebidos=docs_recebidos,
        docs_total=docs_total,
    )
    colaborador.status_label = ex.label
    colaborador.status_hint = ex.hint
    colaborador.status_tone = ex.tone
    return colaborador


def serializar_status_colaborador(
    colaborador: Colaborador,
    *,
    docs_recebidos: int | None = None,
    docs_total: int | None = None,
) -> dict:
    ex = status_exibicao_colaborador(
        colaborador,
        docs_recebidos=docs_recebidos,
        docs_total=docs_total,
    )
    return {
        'status': ex.status,
        'status_display': ex.label,
        'status_hint': ex.hint,
        'status_tone': ex.tone,
    }
