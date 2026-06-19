from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from recursos_humanos.models import Colaborador, DocumentoColaborador
from recursos_humanos.services.alertas_config import obter_configuracao_alertas
from recursos_humanos.services.prazo_contrato import prazos_vencendo


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
    acao_extra: dict = field(default_factory=dict)
    titulo: str = ''
    icone: str = 'fa-bell'
    acao_label: str = ''
    acao_hint: str = ''


def _texto_situacao_prazo(dias: int) -> str:
    if dias < 0:
        return f'{abs(dias)} dias de atraso'
    if dias == 0:
        return 'Vence hoje'
    if dias == 1:
        return 'Vence amanhã'
    return f'Vence em {dias} dias'


def _montar_alerta_documento(doc, dias: int, tipo_alerta: str, acao: str) -> AlertaRH:
    prazo_fmt = doc.vencimento.strftime('%d/%m/%Y')
    nome_doc = doc.tipo.nome
    if dias < 0:
        titulo = f'{nome_doc} venceu em {prazo_fmt}'
        detalhe = nome_doc
    else:
        titulo = f'{nome_doc} vence em {prazo_fmt}'
        detalhe = nome_doc

    return AlertaRH(
        id=f'doc-{doc.pk}',
        colaborador_id=doc.colaborador_id,
        colaborador_nome=doc.colaborador.nome,
        tipo=tipo_alerta,
        detalhe=detalhe,
        prazo=prazo_fmt,
        dias_restantes=dias,
        urgencia=_urgencia_por_dias(dias),
        acao=acao,
        url=_url_colaborador(doc.colaborador_id, tab='documentos', doc_id=doc.pk),
        titulo=titulo,
        icone='fa-exclamation-triangle' if dias < 0 else 'fa-file-alt',
        acao_label='Abrir documentos',
        acao_hint='Abre o perfil na aba Documentos com este item em destaque.',
    )


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


def _url_colaborador(pk: int, *, tab: str | None = None, doc_id: int | None = None) -> str:
    from urllib.parse import urlencode

    params = {'abrir_colaborador': pk}
    if tab:
        params['abrir_colaborador_tab'] = tab
    if doc_id:
        params['abrir_colaborador_doc'] = doc_id
    url = reverse('recursos_humanos:colaboradores_list')
    return f'{url}?{urlencode(params)}'


def _url_admissao(pk: int) -> str:
    return f"{reverse('recursos_humanos:admissao')}?id={pk}"


def _doc_vencido_deve_alertar(dias: int, config) -> bool:
    """Renotifica documentos vencidos a cada N dias (primeiro dia sempre alerta)."""
    dias_atraso = abs(dias)
    n = max(1, config.dias_renotificar_vencidos)
    if dias_atraso <= 1:
        return True
    return dias_atraso % n == 0


def _doc_deve_gerar_alerta(doc: DocumentoColaborador, hoje, dias: int, config) -> bool:
    if doc.vencimento is None or not doc.tipo.tem_validade:
        return False
    if dias < 0:
        return _doc_vencido_deve_alertar(dias, config)
    if doc.colaborador.status == Colaborador.Status.DESLIGADO:
        return False
    limite = config.dias_antecedencia_documentos
    if doc.status == DocumentoColaborador.Status.RECEBIDO and dias > limite:
        return False
    return doc.colaborador.status in (
        Colaborador.Status.ATIVO,
        Colaborador.Status.EM_ADMISSAO,
    )


def gerar_alertas() -> list[AlertaRH]:
    hoje = timezone.localdate()
    config = obter_configuracao_alertas()
    alertas: list[AlertaRH] = []

    docs = DocumentoColaborador.objects.select_related('colaborador', 'tipo').filter(
        tipo__tem_validade=True,
    ).exclude(vencimento__isnull=True)
    for doc in docs:
        dias = (doc.vencimento - hoje).days
        if not _doc_deve_gerar_alerta(doc, hoje, dias, config):
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

        alertas.append(_montar_alerta_documento(doc, dias, tipo_alerta, acao))

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
                    titulo='Admissão aguarda validação do RH',
                    icone='fa-user-check',
                    acao_label='Abrir admissão',
                    acao_hint='Abre o fluxo de admissão na etapa de validação para aprovar ou devolver.',
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
            titulo = 'Documentos pendentes na admissão'
            if nomes_faltando:
                titulo = f'Faltam documentos: {", ".join(nomes_faltando[:2])}'
                if len(nomes_faltando) > 2:
                    titulo += f' e mais {len(nomes_faltando) - 2}'
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
                    titulo=titulo,
                    icone='fa-folder-open',
                    acao_label='Abrir admissão',
                    acao_hint='Abre o fluxo de admissão para conferir o que o candidato ainda precisa enviar.',
                )
            )

    for prazo in prazos_vencendo(dias_antecedencia=config.dias_antecedencia_documentos):
        dias = prazo.dias_restantes()
        if dias < 0:
            urgencia = 'red'
        elif dias <= 7:
            urgencia = 'red'
        else:
            urgencia = 'yellow'
        tipo_prazo = prazo.get_tipo_display()
        prazo_fmt = prazo.data_fim.strftime('%d/%m/%Y')
        if dias < 0:
            titulo = f'{tipo_prazo} venceu em {prazo_fmt}'
        else:
            titulo = f'{tipo_prazo} vence em {prazo_fmt}'

        alertas.append(
            AlertaRH(
                id=f'prazo-{prazo.pk}',
                colaborador_id=prazo.colaborador_id,
                colaborador_nome=prazo.colaborador.nome,
                tipo='Prazo de contrato',
                detalhe=tipo_prazo,
                prazo=prazo_fmt,
                dias_restantes=dias,
                urgencia=urgencia,
                acao='Decidir',
                url=_url_colaborador(prazo.colaborador_id),
                acao_extra={'prazo_id': prazo.pk, 'tipo': 'contrato'},
                titulo=titulo,
                icone='fa-file-signature',
                acao_label='Decidir contrato',
                acao_hint='Abre o formulário para efetivar, converter ou encerrar o prazo do contrato.',
            )
        )

    alertas.sort(key=lambda a: a.dias_restantes)
    return alertas


def contar_alertas() -> int:
    """Contagem para badge nas abas; respeita notificar_sistema da configuração."""
    config = obter_configuracao_alertas()
    if not config.notificar_sistema:
        return 0
    return len(gerar_alertas())


def resumo_alertas(alertas: list[AlertaRH], config=None) -> dict:
    hoje = timezone.localdate()
    cfg = config or obter_configuracao_alertas()
    limite_doc = cfg.dias_antecedencia_documentos
    vencendo = sum(
        1 for a in alertas if a.tipo == 'Documento vencendo' and 0 <= a.dias_restantes <= limite_doc
    )
    vencidos = sum(1 for a in alertas if a.tipo == 'Documento vencido')
    admissoes = sum(1 for a in alertas if a.tipo == 'Admissão em andamento')
    contratos = sum(1 for a in alertas if a.tipo == 'Prazo de contrato')
    treinamentos = sum(
        1 for a in alertas
        if a.tipo == 'Documento vencendo'
        and (
            'nr' in a.detalhe.lower()
            or 'treinamento' in a.detalhe.lower()
        )
    )
    documentos = sum(1 for a in alertas if a.tipo.startswith('Documento'))
    urgentes = sum(1 for a in alertas if a.urgencia == 'red')
    fluxo = admissoes + contratos
    return {
        'vencendo': vencendo,
        'vencidos': vencidos,
        'treinamentos': treinamentos,
        'admissoes': admissoes,
        'contratos': contratos,
        'documentos': documentos,
        'urgentes': urgentes,
        'fluxo': fluxo,
        'dias_antecedencia_documentos': limite_doc,
        'total': len(alertas),
        'hoje': hoje,
    }


def label_urgencia(urgencia: str) -> str:
    return _label_urgencia(urgencia)
