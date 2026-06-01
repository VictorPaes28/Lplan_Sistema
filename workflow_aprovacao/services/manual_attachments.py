"""Upload e exibição de anexos em pedidos manuais da Central."""
from __future__ import annotations

from django.urls import reverse
from django.utils.text import get_valid_filename

from workflow_aprovacao.services.gestao_display import (
    gestao_attachment_icon_class,
    gestao_attachment_icon_tone,
)

MAX_MANUAL_ATTACHMENTS = 10


def _ext_from_nome(nome: str) -> str:
    nome = (nome or '').strip()
    if '.' in nome:
        return nome.rsplit('.', 1)[-1].upper()
    return ''


def save_manual_request_attachments(process, files, uploaded_by):
    """Grava anexos enviados no formulário de pedido manual."""
    from workflow_aprovacao.models import ApprovalProcessAttachment

    saved = []
    for uploaded in files or []:
        if not uploaded:
            continue
        original = get_valid_filename(getattr(uploaded, 'name', '') or 'anexo') or 'anexo'
        saved.append(
            ApprovalProcessAttachment.objects.create(
                process=process,
                file=uploaded,
                original_name=original,
                uploaded_by=uploaded_by,
            )
        )
    return saved


def manual_attachments_for_ui(process) -> list[dict]:
    """Normaliza anexos do processo manual para cards na tela de detalhe."""
    out: list[dict] = []
    for att in process.attachments.all():
        nome = (att.original_name or '').strip()
        if not nome and att.file:
            nome = att.file.name.rsplit('/', 1)[-1]
        if not nome:
            nome = 'Documento anexado'
        ext = _ext_from_nome(nome)
        meta_parts = []
        if ext:
            meta_parts.append(ext)
        if att.created_at:
            meta_parts.append(att.created_at.strftime('%d/%m/%Y %H:%M'))
        if att.uploaded_by:
            meta_parts.append(
                (att.uploaded_by.get_full_name() or '').strip() or att.uploaded_by.username
            )
        out.append(
            {
                'id': att.pk,
                'nome': nome,
                'url': reverse(
                    'workflow_aprovacao:manual_process_attachment',
                    kwargs={'pk': process.pk, 'attachment_pk': att.pk},
                ),
                'extensao': ext,
                'meta': ' · '.join(meta_parts) if meta_parts else 'Documento anexado no pedido manual',
                'icon_class': gestao_attachment_icon_class(ext),
                'icon_tone': gestao_attachment_icon_tone(ext),
            }
        )
    return out
