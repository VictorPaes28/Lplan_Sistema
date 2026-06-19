"""Payload JSON para ações de documento sem recarregar a página."""
from __future__ import annotations

from recursos_humanos.models import DocumentoColaborador
from recursos_humanos.services.admissao import montar_grupos_documentos, resumo_documentos


def _status_ui_doc(doc: DocumentoColaborador) -> str:
    if doc.status == DocumentoColaborador.Status.RECEBIDO:
        return 'ok'
    if doc.status == DocumentoColaborador.Status.PENDENTE:
        return 'pending'
    return 'missing'


def _status_label_doc(doc: DocumentoColaborador) -> str:
    if doc.status == DocumentoColaborador.Status.RECEBIDO:
        return 'Recebido'
    if doc.status == DocumentoColaborador.Status.PENDENTE and doc.arquivo:
        return 'Aguardando aprovação'
    if doc.status == DocumentoColaborador.Status.PENDENTE:
        return 'Pendente'
    return 'Faltando'


def serializar_documento_pos_acao(doc: DocumentoColaborador, user=None) -> dict:
    doc.refresh_from_db()
    colaborador = doc.colaborador
    grupos = montar_grupos_documentos(colaborador)
    resumo = resumo_documentos(grupos)

    grupos_stats = []
    for grupo in grupos:
        recebidos = sum(1 for item in grupo.docs if item.status == 'ok')
        total = len(grupo.docs)
        if total and recebidos == total:
            header_state = 'done'
        elif recebidos == 0:
            header_state = 'missing'
        else:
            header_state = 'warn'
        grupos_stats.append({
            'id': grupo.id,
            'recebidos': recebidos,
            'total': total,
            'header_state': header_state,
        })

    from recursos_humanos.services.admissao import montar_contexto_admissao
    from recursos_humanos.services.admissao_actions import listar_historico_colaborador

    historico = listar_historico_colaborador(colaborador)
    admissao_ctx = montar_contexto_admissao(colaborador, historico, user=user)
    pode_encaminhar = admissao_ctx.get('pode_encaminhar_validacao', False)

    payload = {
        'doc_id': doc.pk,
        'status': _status_ui_doc(doc),
        'status_label': _status_label_doc(doc),
        'observacao': (doc.observacao or '').strip(),
        'tem_arquivo': bool(doc.arquivo),
        'aguardando_aprovacao': bool(
            doc.arquivo and doc.status == DocumentoColaborador.Status.PENDENTE
        ),
        'data_emissao': doc.data_emissao.strftime('%d/%m/%Y') if doc.data_emissao else None,
        'vencimento': doc.vencimento.strftime('%d/%m/%Y') if doc.vencimento else None,
        'resumo': resumo,
        'grupos': grupos_stats,
        'pode_encaminhar_validacao': pode_encaminhar,
        'colaborador_id': colaborador.pk,
    }
    return payload


def resposta_json_documento(ok: bool, msg: str, doc: DocumentoColaborador | None = None, user=None) -> dict:
    data = {'ok': ok, 'message': msg}
    if ok and doc is not None:
        data['doc'] = serializar_documento_pos_acao(doc, user=user)
    return data
