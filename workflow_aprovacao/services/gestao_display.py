"""Formatação de dados GestControll na Central de Aprovações."""
from __future__ import annotations

from django.utils.dateparse import parse_datetime
from django.utils import timezone


def _ext_from_nome(nome: str) -> str:
    nome = (nome or '').strip()
    if '.' in nome:
        return nome.rsplit('.', 1)[-1].upper()
    return ''


def gestao_attachment_icon_class(ext: str) -> str:
    """Classe Font Awesome para o ícone do anexo."""
    ext = (ext or '').upper()
    if ext == 'PDF':
        return 'fa-file-pdf'
    if ext in ('PNG', 'JPG', 'JPEG', 'GIF', 'WEBP', 'SVG', 'BMP'):
        return 'fa-file-image'
    if ext in ('DOC', 'DOCX', 'ODT', 'RTF'):
        return 'fa-file-word'
    if ext in ('XLS', 'XLSX', 'CSV', 'ODS'):
        return 'fa-file-excel'
    if ext in ('ZIP', 'RAR', '7Z'):
        return 'fa-file-archive'
    if ext in ('DWG', 'DXF'):
        return 'fa-drafting-compass'
    return 'fa-file-alt'


def gestao_attachment_icon_tone(ext: str) -> str:
    """Sufixo CSS (wf-attach-card__icon--tone) para cor do ícone."""
    ext = (ext or '').upper()
    if ext == 'PDF':
        return 'pdf'
    if ext in ('PNG', 'JPG', 'JPEG', 'GIF', 'WEBP', 'SVG', 'BMP'):
        return 'image'
    if ext in ('DOC', 'DOCX', 'ODT', 'RTF'):
        return 'doc'
    if ext in ('XLS', 'XLSX', 'CSV', 'ODS'):
        return 'sheet'
    return 'generic'


def _format_uploaded_at(iso: str) -> str:
    if not iso:
        return ''
    raw = str(iso).strip()
    dt = parse_datetime(raw.replace('Z', '+00:00'))
    if not dt:
        return ''
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return dt.strftime('%d/%m/%Y %H:%M')


def gestao_snapshot_attachments_for_ui(anexos: list | None) -> list[dict]:
    """Normaliza anexos do snapshot para cards na tela de detalhe."""
    out: list[dict] = []
    for raw in anexos or []:
        if not isinstance(raw, dict):
            continue
        nome = (raw.get('nome') or '').strip() or 'Sem nome'
        ext = (raw.get('extensao') or '').strip().upper() or _ext_from_nome(nome)
        uploaded = _format_uploaded_at(raw.get('uploaded_at') or '')
        meta_parts = []
        if ext:
            meta_parts.append(ext)
        if raw.get('tamanho'):
            meta_parts.append(str(raw['tamanho']))
        if uploaded:
            meta_parts.append(uploaded)
        if raw.get('enviado_por'):
            meta_parts.append(str(raw['enviado_por']))
        versao = raw.get('versao_reaprovacao')
        if versao not in (None, '', 0, '0'):
            meta_parts.append(f'Reaprovação v{versao}')
        out.append(
            {
                'id': raw.get('id'),
                'nome': nome,
                'url': (raw.get('url') or '').strip(),
                'extensao': ext,
                'meta': ' · '.join(meta_parts) if meta_parts else 'Documento anexado no GestControll',
                'icon_class': gestao_attachment_icon_class(ext),
                'icon_tone': gestao_attachment_icon_tone(ext),
            }
        )
    return out
