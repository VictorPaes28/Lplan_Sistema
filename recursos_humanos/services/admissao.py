"""Montagem do conteúdo visual do fluxo de admissão (leitura a partir dos models)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from recursos_humanos.models import Colaborador, ContratoAdmissao, DocumentoColaborador, PrazoContrato


@dataclass
class DocGrupoItem:
    pk: int
    nome: str
    status: str  # ok | pending | missing
    observacao: str = ''
    instrucoes_portal: str = ''
    tem_arquivo: bool = False
    tem_validade: bool = False
    dias_validade: int | None = None
    data_emissao: object = None
    vencimento: object = None
    arquivo_url: str = ''
    arquivo_nome: str = ''
    arquivo_is_image: bool = False
    arquivo_is_pdf: bool = False
    arquivo_icon: str = 'fa-file'
    aguardando_aprovacao: bool = False
    reenvio_solicitado: bool = False
    vencido: bool = False
    alerta_vencimento: bool = False
    dias_restantes: int | None = None
    pode_solicitar_reenvio: bool = False


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
    from recursos_humanos.services.documentos import documento_status_fluxo_ok

    if doc.reenvio_solicitado:
        return 'pending'
    if documento_status_fluxo_ok(doc):
        return 'ok'
    if doc.status == DocumentoColaborador.Status.PENDENTE:
        return 'pending'
    return 'missing'


def _meta_arquivo_doc(doc: DocumentoColaborador) -> dict:
    if not doc.arquivo:
        return {}
    nome = doc.arquivo.name.rsplit('/', 1)[-1]
    partes = nome.rsplit('.', 1)
    ext = partes[-1].lower() if len(partes) > 1 else ''
    icones = {
        'pdf': 'fa-file-pdf',
        'doc': 'fa-file-word',
        'docx': 'fa-file-word',
        'xls': 'fa-file-excel',
        'xlsx': 'fa-file-excel',
    }
    return {
        'url': doc.arquivo.url,
        'nome': nome,
        'is_image': ext in ('jpg', 'jpeg', 'png', 'webp', 'gif'),
        'is_pdf': ext == 'pdf',
        'icon': icones.get(ext, 'fa-file'),
    }


def _observacao_padrao(doc: DocumentoColaborador) -> str:
    from recursos_humanos.services.documentos import documento_esta_vencido

    if doc.reenvio_solicitado:
        return 'Reenvio solicitado — aguardando novo arquivo do colaborador'
    if documento_esta_vencido(doc):
        return 'Documento vencido — solicite reenvio ao colaborador'
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


def _categoria_documento_por_nome(nome: str) -> str:
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


def _categoria_documento(tipo) -> str:
    """Usa categoria explícita; se for o padrão «outros», infere pelo nome (legado e testes)."""
    cat = getattr(tipo, 'categoria', None) or ''
    if cat and cat != 'outros':
        return cat
    return _categoria_documento_por_nome(tipo.nome)


def montar_grupos_documentos(colaborador: Colaborador) -> list[DocGrupo]:
    from recursos_humanos.services.documentos import (
        documento_alerta_vencimento,
        documento_dias_restantes,
        documento_esta_vencido,
        documento_elegivel_reenvio,
    )

    buckets: dict[str, list[DocGrupoItem]] = {g[0]: [] for g in GRUPOS_META}
    docs = colaborador.documentos.select_related('tipo').order_by('tipo__ordem', 'tipo__nome')
    for doc in docs:
        cat = _categoria_documento(doc.tipo)
        meta = _meta_arquivo_doc(doc)
        elegivel_reenvio, _ = documento_elegivel_reenvio(doc)
        obs = _observacao_padrao(doc)
        instrucoes = (doc.tipo.instrucoes_portal or '').strip()
        buckets[cat].append(
            DocGrupoItem(
                pk=doc.pk,
                nome=doc.tipo.nome,
                status=_status_ui(doc),
                observacao=obs,
                instrucoes_portal=instrucoes,
                tem_arquivo=bool(doc.arquivo),
                tem_validade=doc.tipo.tem_validade,
                dias_validade=doc.tipo.dias_validade,
                data_emissao=doc.data_emissao,
                vencimento=doc.vencimento,
                arquivo_url=meta.get('url', ''),
                arquivo_nome=meta.get('nome', ''),
                arquivo_is_image=meta.get('is_image', False),
                arquivo_is_pdf=meta.get('is_pdf', False),
                arquivo_icon=meta.get('icon', 'fa-file'),
                aguardando_aprovacao=(
                    bool(doc.arquivo)
                    and doc.status == DocumentoColaborador.Status.PENDENTE
                ),
                reenvio_solicitado=doc.reenvio_solicitado,
                vencido=documento_esta_vencido(doc),
                alerta_vencimento=documento_alerta_vencimento(doc),
                dias_restantes=documento_dias_restantes(doc),
                pode_solicitar_reenvio=elegivel_reenvio,
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


def formatar_salario_br(valor) -> str:
    """Formata valor monetário no padrão brasileiro (ex.: 10.000,00)."""
    if valor is None:
        return '—'
    bruto = str(valor).strip()
    if not bruto or bruto == '—':
        return '—'
    texto = re.sub(r'[Rr]\$\s*', '', bruto).strip()
    if ',' in texto:
        texto = texto.replace('.', '').replace(',', '.')
    elif '.' in texto:
        partes = texto.split('.')
        if len(partes) > 1 and len(partes[-1]) == 3 and partes[-1].isdigit():
            texto = ''.join(partes)
    try:
        numero = Decimal(texto)
    except InvalidOperation:
        return bruto
    sinal = '-' if numero < 0 else ''
    absoluto = abs(numero).quantize(Decimal('0.01'))
    inteiro, _, decimais = f'{absoluto:.2f}'.partition('.')
    inteiro_fmt = f'{int(inteiro):,}'.replace(',', '.')
    return f'{sinal}{inteiro_fmt},{decimais}'


def _extrair_autor_historico(historico, palavras_chave: tuple[str, ...]) -> str:
    for ev in historico:
        texto = f'{ev.descricao} {ev.autor}'.lower()
        if any(p in texto for p in palavras_chave):
            return ev.autor or ev.descricao
    return ''


def _contexto_aprovacao_requisicao(colaborador: Colaborador) -> dict:
    if not colaborador.requisicao_aprovada_gestor:
        return {
            'por': '',
            'em': None,
            'assinatura': '',
            'tem_assinatura': False,
        }
    aprovador = colaborador.requisicao_aprovada_por
    if aprovador:
        nome = aprovador.get_full_name() or aprovador.username
    elif colaborador.gestor_aprovador:
        nome = colaborador.gestor_aprovador
    else:
        nome = '—'
    assinatura = (colaborador.requisicao_aprovacao_assinatura or '').strip()
    return {
        'por': nome,
        'em': colaborador.requisicao_aprovada_em,
        'assinatura': assinatura,
        'tem_assinatura': bool(assinatura),
    }


def _itens_dados_candidato(colaborador: Colaborador) -> list[tuple[str, str]]:
    itens: list[tuple[str, str]] = []
    if colaborador.rg:
        itens.append(('RG', colaborador.rg))
    if colaborador.data_nascimento:
        itens.append(('Data de nascimento', colaborador.data_nascimento.strftime('%d/%m/%Y')))
    if colaborador.pis:
        itens.append(('PIS', colaborador.pis))
    if colaborador.endereco:
        itens.append(('Endereço', colaborador.endereco))
    if colaborador.dados_bancarios:
        itens.append(('Conta bancária', colaborador.dados_bancarios))
    if colaborador.escolaridade:
        itens.append(('Escolaridade', colaborador.escolaridade))
    if colaborador.tamanho_camisa:
        itens.append(('Tam. camisa', colaborador.tamanho_camisa))
    if colaborador.tamanho_bota:
        itens.append(('Tam. bota', colaborador.tamanho_bota))
    if colaborador.empresa:
        itens.append(('Empresa responsável', colaborador.empresa))
    return itens


def contexto_etapa_requisicao(colaborador: Colaborador, historico, user=None) -> dict:
    from recursos_humanos.services.admissao_actions import (
        garantir_requisicao_criada_por,
        nomes_aprovadores_requisicao,
    )
    from recursos_humanos.services.papeis_fluxo import responsavel_admissao_colaborador
    from recursos_humanos.services.reembolsos import reembolsos_para_contexto

    hist = list(historico)
    garantir_requisicao_criada_por(colaborador)
    responsavel = responsavel_admissao_colaborador(colaborador)
    solicitante = responsavel or _extrair_autor_historico(
        hist, ('requisição criada', 'requisicao criada', 'rh —', 'rh -'),
    )
    obras = list(colaborador.obras.values_list('nome', flat=True))
    ctx = {
        'solicitante': solicitante or 'RH',
        'responsavel': responsavel,
        'gestor': responsavel,
        'gestor_user_id': colaborador.requisicao_criada_por_id or colaborador.gestor_aprovador_user_id,
        'aprovadores': ', '.join(nomes_aprovadores_requisicao(colaborador)) or '—',
        'requisicao_aprovada': colaborador.requisicao_aprovada_gestor,
        'requisicao_reprovada': colaborador.requisicao_reprovada,
        'motivo_reprovacao': colaborador.requisicao_motivo_reprovacao,
        'cargo_rh': colaborador.cargo_rh.nome if colaborador.cargo_rh_id else '—',
        'obras': ', '.join(obras) if obras else '—',
        'data_requisicao': colaborador.data_admissao,
        'motivo': colaborador.motivo_admissao or 'Nova contratação',
        'tipo_contrato': colaborador.tipo_contrato or 'CLT',
        'salario': formatar_salario_br(colaborador.salario),
        'deslocamento_origem': colaborador.deslocamento_origem or '—',
        'deslocamento_destino': colaborador.deslocamento_destino or '—',
        'reembolsos': reembolsos_para_contexto(colaborador),
        'email': colaborador.email or '—',
        'telefone': colaborador.telefone or '—',
        'observacoes': colaborador.observacoes_requisicao,
        'dados_candidato_itens': _itens_dados_candidato(colaborador),
        'aprovacao': _contexto_aprovacao_requisicao(colaborador),
        'pode_aprovar': False,
        'pode_reprovar': False,
        'pode_corrigir': False,
    }
    if user is not None:
        from recursos_humanos.services.admissao_actions import (
            _usuario_pode_aprovar_requisicao,
            _usuario_pode_corrigir_requisicao,
        )

        ctx['pode_aprovar'] = (
            not colaborador.requisicao_aprovada_gestor
            and not colaborador.requisicao_reprovada
            and _usuario_pode_aprovar_requisicao(colaborador, user)
        )
        ctx['pode_reprovar'] = ctx['pode_aprovar']
        if colaborador.requisicao_reprovada:
            garantir_requisicao_criada_por(colaborador)
        ctx['pode_corrigir'] = (
            colaborador.requisicao_reprovada
            and not colaborador.requisicao_aprovada_gestor
            and _usuario_pode_corrigir_requisicao(colaborador, user)
        )
    return ctx


def _doc_por_palavras(colaborador: Colaborador, *palavras: str) -> DocumentoColaborador | None:
    for doc in colaborador.documentos.select_related('tipo'):
        nome = doc.tipo.nome.lower()
        if all(p in nome for p in palavras):
            return doc
    return None


def _checklist_hint_documento(doc: DocumentoColaborador, hoje) -> str:
    if doc.status == DocumentoColaborador.Status.RECEBIDO:
        if doc.vencimento and doc.vencimento < hoje:
            return 'Vencido'
        return ''
    if doc.status == DocumentoColaborador.Status.PENDENTE:
        if doc.arquivo:
            return 'Aguardando aprovação'
        return 'Pendente'
    return 'Faltando'


def checklist_aprovacao_rh(colaborador: Colaborador) -> list[dict]:
    hoje = timezone.localdate()
    docs = colaborador.documentos.select_related('tipo').order_by('tipo__ordem', 'tipo__nome')
    out = []
    for doc in docs:
        meta = _meta_arquivo_doc(doc)
        hint = _checklist_hint_documento(doc, hoje)
        ok = (
            doc.status == DocumentoColaborador.Status.RECEBIDO
            and not hint
            and not doc.reenvio_solicitado
        )
        out.append({
            'label': doc.tipo.nome,
            'ok': ok,
            'hint': hint,
            'obrigatorio': doc.tipo.obrigatorio,
            'tem_arquivo': bool(doc.arquivo),
            'arquivo_url': meta.get('url', ''),
            'arquivo_nome': meta.get('nome', ''),
            'arquivo_is_image': meta.get('is_image', False),
            'arquivo_is_pdf': meta.get('is_pdf', False),
            'arquivo_icon': meta.get('icon', 'fa-file'),
        })
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
    from recursos_humanos.services.reembolsos import reembolsos_para_contexto

    obras = list(colaborador.obras.values_list('nome', flat=True))
    inicio = colaborador.data_admissao
    data_admissao_oficial = None
    data_inicio_prevista = inicio
    try:
        contrato = colaborador.contrato_admissao
    except ContratoAdmissao.DoesNotExist:
        contrato = None
    if contrato:
        data_admissao_oficial = contrato.data_admissao_oficial
    prazo_ativo = colaborador.prazos_contrato.filter(
        status=PrazoContrato.Status.ATIVO,
    ).first()
    contrato_enviado = colaborador.historico_admissao.filter(
        etapa=4,
        descricao__icontains='Contrato enviado para assinatura',
    ).exists()
    return {
        'tipo_contrato': colaborador.tipo_contrato or 'CLT',
        'cargo': colaborador.cargo,
        'obra': ', '.join(obras) if obras else '—',
        'data_inicio': inicio,
        'data_inicio_prevista': data_inicio_prevista,
        'data_admissao_oficial': data_admissao_oficial,
        'salario': formatar_salario_br(colaborador.salario),
        'deslocamento_origem': colaborador.deslocamento_origem or '—',
        'deslocamento_destino': colaborador.deslocamento_destino or '—',
        'reembolsos': reembolsos_para_contexto(colaborador),
        'contrato': contrato,
        'prazo_ativo': prazo_ativo,
        'contrato_enviado': contrato_enviado,
    }


def montar_contexto_admissao(colaborador: Colaborador, historico, user=None) -> dict:
    from recursos_humanos.services.documentos import documentacao_fluxo_completa
    from recursos_humanos.services.papeis_fluxo import _usuario_eh_rh

    grupos = montar_grupos_documentos(colaborador)
    resumo = resumo_documentos(grupos)
    etapa = colaborador.etapa_admissao
    usuario_rh_pode = _usuario_eh_rh(user) if user else False
    return {
        'etapa_atual': etapa,
        'doc_grupos': grupos,
        'doc_resumo': resumo,
        'usuario_rh_pode': usuario_rh_pode,
        'pode_encaminhar_validacao': (
            etapa == 2
            and resumo.get('completo')
            and documentacao_fluxo_completa(colaborador)
        ),
        'etapa_1': contexto_etapa_requisicao(colaborador, historico, user=user),
        'etapa_3': contexto_etapa_aprovacao(colaborador, resumo),
        'etapa_4': contexto_etapa_contrato(colaborador),
    }
