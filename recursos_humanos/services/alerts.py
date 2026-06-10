from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from recursos_humanos.models import Colaborador, DocumentoColaborador


@dataclass
class AlertaRH:
    id: str
    colaborador_id: int
    colaborador_nome: str
    tipo: str
    detalhe: str
    prazo: str
    dias_restantes: int
    urgencia: str  # red, yellow, green
    acao: str
    url: str


def _urgencia_por_dias(dias: int) -> str:
    if dias < 0:
        return 'red'
    if dias <= 7:
        return 'red'
    if dias <= 30:
        return 'yellow'
    return 'green'


def _label_urgencia(urgencia: str) -> str:
    return {'red': 'Urgente', 'yellow': 'Atenção', 'green': 'Informativo'}.get(urgencia, 'Informativo')


def _url_colaborador(pk: int) -> str:
    return reverse('recursos_humanos:colaborador_detalhe', args=[pk])


def _url_admissao(pk: int) -> str:
    return f"{reverse('recursos_humanos:admissao')}?id={pk}"


def _doc_deve_gerar_alerta(doc: DocumentoColaborador, hoje, dias: int) -> bool:
    """Regras de negócio: ativos/admissão para vencimentos futuros; vencidos para todos."""
    if doc.vencimento is None:
        return False
    if dias < 0:
        return True
    if doc.colaborador.status == Colaborador.Status.DESLIGADO:
        return False
    if doc.status == DocumentoColaborador.Status.RECEBIDO and dias > 30:
        return False
    return doc.colaborador.status in (
        Colaborador.Status.ATIVO,
        Colaborador.Status.EM_ADMISSAO,
    )


def gerar_alertas() -> list[AlertaRH]:
    hoje = timezone.localdate()
    alertas: list[AlertaRH] = []

    docs = DocumentoColaborador.objects.select_related('colaborador', 'tipo').exclude(
        vencimento__isnull=True,
    )
    for doc in docs:
        dias = (doc.vencimento - hoje).days
        if not _doc_deve_gerar_alerta(doc, hoje, dias):
            continue

        if doc.status == DocumentoColaborador.Status.RECEBIDO and dias >= 0:
            tipo_alerta = 'Documento vencendo'
            acao = 'Agendar' if dias > 7 else 'Renovar'
        elif dias < 0:
            tipo_alerta = 'Documento vencido'
            acao = 'Regularizar'
        else:
            tipo_alerta = 'Documento vencendo'
            acao = 'Renovar' if dias <= 7 else 'Agendar'

        alertas.append(
            AlertaRH(
                id=f'doc-{doc.pk}',
                colaborador_id=doc.colaborador_id,
                colaborador_nome=doc.colaborador.nome,
                tipo=tipo_alerta,
                detalhe=doc.tipo.nome + (f' (venceu {doc.vencimento:%d/%m/%Y})' if dias < 0 else ''),
                prazo=doc.vencimento.strftime('%d/%m/%Y'),
                dias_restantes=dias,
                urgencia=_urgencia_por_dias(dias),
                acao=acao,
                url=_url_colaborador(doc.colaborador_id),
            )
        )

    for colab in Colaborador.objects.filter(status=Colaborador.Status.EM_ADMISSAO):
        faltando = colab.documentos.filter(status=DocumentoColaborador.Status.FALTANDO).count()
        pendentes = colab.documentos.filter(status=DocumentoColaborador.Status.PENDENTE).count()
        etapa = colab.etapa_admissao

        if etapa >= 3:
            prazo = (colab.data_admissao + timedelta(days=9)) if colab.data_admissao else (hoje + timedelta(days=1))
            dias = (prazo - hoje).days
            alertas.append(
                AlertaRH(
                    id=f'adm-{colab.pk}',
                    colaborador_id=colab.pk,
                    colaborador_nome=colab.nome,
                    tipo='Admissão em andamento',
                    detalhe='Aguardando aprovação do RH',
                    prazo=prazo.strftime('%d/%m/%Y'),
                    dias_restantes=dias,
                    urgencia=_urgencia_por_dias(dias),
                    acao='Aprovar',
                    url=_url_admissao(colab.pk),
                )
            )
        elif faltando or pendentes:
            prazo = colab.proximo_prazo() or (hoje + timedelta(days=7))
            dias = (prazo - hoje).days
            nomes_faltando = list(
                colab.documentos.filter(status=DocumentoColaborador.Status.FALTANDO)
                .values_list('tipo__nome', flat=True)[:3]
            )
            detalhe = 'Documentos pendentes'
            if nomes_faltando:
                detalhe += ': ' + ', '.join(nomes_faltando)
            alertas.append(
                AlertaRH(
                    id=f'adm-{colab.pk}',
                    colaborador_id=colab.pk,
                    colaborador_nome=colab.nome,
                    tipo='Admissão em andamento',
                    detalhe=detalhe,
                    prazo=prazo.strftime('%d/%m/%Y'),
                    dias_restantes=dias,
                    urgencia=_urgencia_por_dias(dias),
                    acao='Ver admissão',
                    url=_url_admissao(colab.pk),
                )
            )

    alertas.sort(key=lambda a: a.dias_restantes)
    return alertas


def contar_alertas() -> int:
    """Contagem leve para badge nas abas (reutiliza a mesma regra de negócio)."""
    return len(gerar_alertas())


def resumo_alertas(alertas: list[AlertaRH]) -> dict:
    hoje = timezone.localdate()
    vencendo_7 = sum(
        1 for a in alertas if a.tipo == 'Documento vencendo' and 0 <= a.dias_restantes <= 7
    )
    vencidos = sum(1 for a in alertas if a.tipo == 'Documento vencido')
    admissoes = sum(1 for a in alertas if a.tipo == 'Admissão em andamento')
    treinamentos = sum(
        1
        for a in alertas
        if 'NR-' in a.detalhe and a.tipo == 'Documento vencendo' and a.dias_restantes > 7
    )
    return {
        'vencendo_7': vencendo_7,
        'vencidos': vencidos,
        'treinamentos': treinamentos,
        'admissoes': admissoes,
        'total': len(alertas),
        'hoje': hoje,
    }


def label_urgencia(urgencia: str) -> str:
    return _label_urgencia(urgencia)
