"""Montagem do conteúdo visual do fluxo de admissão (leitura a partir dos models)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from django.utils import timezone

from recursos_humanos.models import Colaborador, DocumentoColaborador


@dataclass
class DocGrupoItem:
    pk: int
    nome: str
    status: str  # ok | pending | missing
    observacao: str = ''
    tem_arquivo: bool = False


@dataclass
class DocGrupo:
    id: str
    label: str
    icon: str
    tone: str
    docs: list[DocGrupoItem] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.docs)

    @property
    def recebidos(self) -> int:
        return sum(1 for d in self.docs if d.status == 'ok')

    @property
    def header_state(self) -> str:
        if self.total == 0:
            return 'empty'
        if self.recebidos == self.total:
            return 'done'
        if any(d.status == 'missing' for d in self.docs):
            return 'missing'
        return 'pending'


GRUPOS_META = (
    ('pessoais', 'Documentos Pessoais', 'fa-user', 'blue'),
    ('comprovantes', 'Comprovantes', 'fa-building', 'purple'),
    ('saude', 'Saúde e Segurança', 'fa-stethoscope', 'red'),
    ('treinamentos', 'Treinamentos e NRs', 'fa-book', 'green'),
    ('outros', 'Outros documentos', 'fa-folder', 'gray'),
)


def _status_ui(doc: DocumentoColaborador) -> str:
    if doc.status == DocumentoColaborador.Status.RECEBIDO:
        return 'ok'
    if doc.status == DocumentoColaborador.Status.PENDENTE:
        return 'pending'
    return 'missing'


def _observacao_padrao(doc: DocumentoColaborador) -> str:
    if doc.observacao:
        return doc.observacao
    nome = doc.tipo.nome.lower()
    if doc.status == DocumentoColaborador.Status.PENDENTE and 'banc' in nome:
        return 'Aguardando confirmação do banco'
    if doc.status == DocumentoColaborador.Status.FALTANDO and 'aso' in nome:
        return 'Exame admissional a agendar'
    if doc.status == DocumentoColaborador.Status.FALTANDO and 'nr-' in nome:
        return 'Obrigatório para o cargo'
    return ''


def _categoria_documento(nome: str) -> str:
    n = nome.lower()
    if 'aso' in n or 'saúde' in n or 'saude' in n:
        return 'saude'
    if 'nr-' in n or n.startswith('nr '):
        return 'treinamentos'
    if any(k in n for k in ('comprovante', 'fgts', 'banc')):
        return 'comprovantes'
    if any(
        k in n
        for k in (
            'rg',
            'cpf',
            'título',
            'titulo',
            'certidão',
            'certidao',
            'pis',
            'ctps',
            'filhos',
            'escolaridade',
        )
    ):
        return 'pessoais'
    return 'outros'


def montar_grupos_documentos(colaborador: Colaborador) -> list[DocGrupo]:
    buckets: dict[str, list[DocGrupoItem]] = {g[0]: [] for g in GRUPOS_META}
    docs = colaborador.documentos.select_related('tipo').order_by('tipo__ordem', 'tipo__nome')
    for doc in docs:
        cat = _categoria_documento(doc.tipo.nome)
        buckets[cat].append(
            DocGrupoItem(
                pk=doc.pk,
                nome=doc.tipo.nome,
                status=_status_ui(doc),
                observacao=_observacao_padrao(doc),
                tem_arquivo=bool(doc.arquivo),
            )
        )

    grupos: list[DocGrupo] = []
    for gid, label, icon, tone in GRUPOS_META:
        items = buckets[gid]
        if not items:
            continue
        grupos.append(DocGrupo(id=gid, label=label, icon=icon, tone=tone, docs=items))
    return grupos


def resumo_documentos(grupos: list[DocGrupo]) -> dict:
    itens = [d for g in grupos for d in g.docs]
    total = len(itens)
    recebidos = sum(1 for d in itens if d.status == 'ok')
    return {
        'total': total,
        'recebidos': recebidos,
        'faltando': total - recebidos,
        'completo': total > 0 and recebidos == total,
    }


def _extrair_autor_historico(historico, palavras_chave: tuple[str, ...]) -> str:
    for ev in historico:
        texto = f'{ev.descricao} {ev.autor}'.lower()
        if any(p in texto for p in palavras_chave):
            return ev.autor or ev.descricao
    return ''


def contexto_etapa_requisicao(colaborador: Colaborador, historico) -> dict:
    hist = list(historico)
    solicitante = _extrair_autor_historico(hist, ('requisição criada', 'requisicao criada', 'rh —', 'rh -'))
    gestor = colaborador.gestor_aprovador or _extrair_autor_historico(hist, ('gestor', 'aprovado', 'entrevista'))
    return {
        'solicitante': solicitante or 'RH',
        'gestor': gestor or 'Gestor responsável',
        'data_requisicao': colaborador.data_admissao,
        'motivo': colaborador.motivo_admissao or 'Nova contratação',
        'tipo_contrato': colaborador.tipo_contrato or 'CLT',
        'salario': colaborador.salario or '—',
        'observacoes': colaborador.observacoes_requisicao,
    }


def _doc_por_palavras(colaborador: Colaborador, *palavras: str) -> DocumentoColaborador | None:
    for doc in colaborador.documentos.select_related('tipo'):
        nome = doc.tipo.nome.lower()
        if all(p in nome for p in palavras):
            return doc
    return None


def checklist_aprovacao_rh(colaborador: Colaborador) -> list[dict]:
    checks = [
        ('CPF válido', _doc_por_palavras(colaborador, 'cpf')),
        ('CTPS sem pendências', _doc_por_palavras(colaborador, 'ctps')),
        ('ASO dentro da validade', _doc_por_palavras(colaborador, 'aso')),
        ('NR obrigatória concluída', _doc_por_palavras(colaborador, 'nr-')),
    ]
    out = []
    for label, doc in checks:
        ok = doc is not None and doc.status == DocumentoColaborador.Status.RECEBIDO
        out.append({'label': label, 'ok': ok})
    return out


def contexto_etapa_aprovacao(colaborador: Colaborador, resumo: dict) -> dict:
    hoje = timezone.localdate()
    prazo = (colaborador.data_admissao + timedelta(days=9)) if colaborador.data_admissao else (hoje + timedelta(days=1))
    return {
        'prazo_analise': prazo,
        'docs_conferidos': f"{resumo['recebidos']}/{resumo['total']}" if resumo['total'] else '—',
        'analista': 'RH — equipe de admissão',
        'checklist': checklist_aprovacao_rh(colaborador),
    }


def contexto_etapa_contrato(colaborador: Colaborador) -> dict:
    obras = list(colaborador.obras.values_list('nome', flat=True))
    inicio = colaborador.data_admissao
    return {
        'tipo_contrato': colaborador.tipo_contrato or 'CLT',
        'cargo': colaborador.cargo,
        'obra': obras[0] if obras else '—',
        'data_inicio': inicio,
        'salario': colaborador.salario or '—',
    }


def montar_contexto_admissao(colaborador: Colaborador, historico) -> dict:
    grupos = montar_grupos_documentos(colaborador)
    resumo = resumo_documentos(grupos)
    etapa = colaborador.etapa_admissao
    return {
        'etapa_atual': etapa,
        'doc_grupos': grupos,
        'doc_resumo': resumo,
        'etapa_1': contexto_etapa_requisicao(colaborador, historico),
        'etapa_3': contexto_etapa_aprovacao(colaborador, resumo),
        'etapa_4': contexto_etapa_contrato(colaborador),
    }
