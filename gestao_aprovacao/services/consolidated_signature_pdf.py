"""Consolida anexos do pedido em um único PDF com página de assinatura ao final."""

from __future__ import annotations

import base64
import io
import logging
import os
from typing import Iterable

logger = logging.getLogger(__name__)

from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from gestao_aprovacao.models import Approval, Attachment, WorkOrder
from gestao_aprovacao.services.attachment_versions import ordered_attachments_for_consolidation
from gestao_aprovacao.signature_utils import validate_signature_data

try:
    from pypdf import PdfMerger, PdfReader
except ImportError:  # pragma: no cover — PyPDF2 3.x
    from PyPDF2 import PdfMerger, PdfReader  # type: ignore

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore

PDF_EXT = '.pdf'
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif'}
BLOCKED_EXTS = {'.doc', '.docx', '.xls', '.xlsx', '.zip', '.rar', '.7z'}


class ConsolidationError(Exception):
    """Erro de negócio ao montar o PDF consolidado."""


class NoAttachmentsError(ConsolidationError):
    pass


class UnsupportedAttachmentsError(ConsolidationError):
    def __init__(self, filenames: list[str]):
        self.filenames = filenames
        joined = ', '.join(filenames)
        super().__init__(
            f'Não é possível incluir no PDF os anexos: {joined}. '
            'Converta-os para PDF ou imagem (JPG/PNG) antes de consolidar.'
        )


class InvalidAttachmentOrderError(ConsolidationError):
    pass


def _attachment_ext(attachment) -> str:
    name = (attachment.nome or '').strip()
    if not name and attachment.arquivo:
        name = os.path.basename(attachment.arquivo.name)
    return os.path.splitext(name.lower())[1]


def _validate_attachments(attachments: Iterable[Attachment]) -> None:
    items = list(attachments)
    if not items:
        raise NoAttachmentsError(
            'Este pedido não possui documentos corrigidos para consolidar. '
            'Adicione os arquivos do novo envio antes de gerar o PDF.'
        )
    unsupported = [
        att.get_nome_display()
        for att in items
        if _attachment_ext(att) in BLOCKED_EXTS
    ]
    if unsupported:
        raise UnsupportedAttachmentsError(unsupported)


def _reorder_attachments(
    attachments: list[Attachment],
    attachment_order: list[int] | None,
) -> list[Attachment]:
    if not attachment_order:
        return attachments
    by_id = {att.pk: att for att in attachments}
    expected_ids = set(by_id.keys())
    requested_ids = set(attachment_order)
    if requested_ids != expected_ids:
        raise InvalidAttachmentOrderError(
            'A lista de anexos foi alterada. Reabra a ordenação e tente novamente.'
        )
    reordered: list[Attachment] = []
    seen: set[int] = set()
    for att_id in attachment_order:
        if att_id in seen:
            continue
        att = by_id.get(att_id)
        if att is None:
            raise InvalidAttachmentOrderError(
                'A lista de anexos foi alterada. Reabra a ordenação e tente novamente.'
            )
        reordered.append(att)
        seen.add(att_id)
    return reordered


def _read_attachment_bytes(attachment: Attachment) -> bytes:
    attachment.arquivo.open('rb')
    try:
        return attachment.arquivo.read()
    finally:
        attachment.arquivo.close()


def _pdf_bytes_from_attachment(attachment: Attachment) -> bytes:
    ext = _attachment_ext(attachment)
    raw = _read_attachment_bytes(attachment)
    if ext == PDF_EXT:
        return raw
    if ext in IMAGE_EXTS:
        return _image_bytes_to_pdf(raw)
    raise UnsupportedAttachmentsError([attachment.get_nome_display()])


def _image_bytes_to_pdf(image_bytes: bytes) -> bytes:
    if Image is None:
        raise ConsolidationError(
            'Conversão de imagem indisponível (Pillow não instalado).'
        )
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    iw, ih = img.size
    margin = 36
    max_w = page_w - 2 * margin
    max_h = page_h - 2 * margin
    scale = min(max_w / iw, max_h / ih, 1.0)
    nw, nh = iw * scale, ih * scale
    x = (page_w - nw) / 2
    y = (page_h - nh) / 2
    jpeg_buf = io.BytesIO()
    img.save(jpeg_buf, format='JPEG', quality=88)
    jpeg_buf.seek(0)
    c.drawImage(ImageReader(jpeg_buf), x, y, width=nw, height=nh)
    c.showPage()
    c.save()
    return buf.getvalue()


def _merge_pdf_parts(parts: list[bytes]) -> bytes:
    merger = PdfMerger()
    try:
        for part in parts:
            merger.append(PdfReader(io.BytesIO(part)))
        out = io.BytesIO()
        merger.write(out)
        return out.getvalue()
    finally:
        merger.close()


def _signature_image_size(signature_data: str, *, max_w: float = 200, max_h: float = 38) -> tuple[float, float]:
    """Retorna largura/altura em pontos para desenhar a assinatura."""
    if not signature_data.startswith('data:image/png;base64,'):
        return 0.0, 0.0
    try:
        raw = base64.b64decode(signature_data.split(',', 1)[1])
        img = ImageReader(io.BytesIO(raw))
        iw, ih = img.getSize()
        if not iw or not ih:
            return 0.0, 0.0
        scale = min(max_w / iw, max_h / ih, 1.0)
        return iw * scale, ih * scale
    except Exception:
        return 0.0, 0.0


def build_signature_page_pdf(
    *,
    work_order: WorkOrder,
    signer_name: str,
    signature_data: str,
    signed_at=None,
) -> bytes:
    signature_data = validate_signature_data(signature_data)
    when = signed_at or timezone.now()
    if timezone.is_naive(when):
        when = timezone.make_aware(when, timezone.get_current_timezone())

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    margin = 56

    ink = (0.07, 0.09, 0.13)
    muted = (0.42, 0.47, 0.53)
    faint = (0.58, 0.62, 0.68)
    rule = (0.82, 0.85, 0.88)

    y = h - margin
    codigo = work_order.codigo or '—'
    tipo = (work_order.get_tipo_solicitacao_display() or '').strip()

    # Código
    c.setFillColorRGB(*ink)
    c.setFont('Helvetica-Bold', 12)
    c.drawString(margin, y, codigo)
    y -= 16

    # Tipo do pedido (linha própria — mais legível que “· Contrato” ao lado)
    if tipo:
        c.setFillColorRGB(*ink)
        c.setFont('Helvetica', 9.5)
        c.drawString(margin, y, tipo)
        y -= 14

    sub_parts = []
    credor = (work_order.nome_credor or '').strip()
    if credor:
        sub_parts.append(credor)
    obra = work_order.obra
    if obra:
        nome_obra = (obra.nome or '').strip()
        if nome_obra:
            sub_parts.append(nome_obra)
    if sub_parts:
        c.setFillColorRGB(*muted)
        c.setFont('Helvetica', 8)
        c.drawString(margin, y, ' · '.join(sub_parts))
        y -= 13

    y -= 4
    c.setStrokeColorRGB(*rule)
    c.setLineWidth(0.5)
    c.line(margin, y, w - margin, y)
    y -= 26

    # Assinado por
    c.setFillColorRGB(*muted)
    c.setFont('Helvetica', 7.5)
    c.drawString(margin, y, 'Assinado por')
    y -= 11
    c.setFillColorRGB(*ink)
    c.setFont('Helvetica-Bold', 10)
    c.drawString(margin, y, signer_name or '—')
    y -= 14

    # Assinatura sobre linha (sem caixa)
    sw, sh = _signature_image_size(signature_data, max_w=200, max_h=36)
    gap = 3
    line_w = max((sw + 16) if sw else 0, 168)
    line_y = y - sh - gap if sh else y - 22

    if sh and signature_data.startswith('data:image/png;base64,'):
        try:
            raw = base64.b64decode(signature_data.split(',', 1)[1])
            img = ImageReader(io.BytesIO(raw))
            c.drawImage(img, margin, line_y + gap, width=sw, height=sh, mask='auto')
        except Exception:
            sh = 0.0

    c.setStrokeColorRGB(*ink)
    c.setLineWidth(0.85)
    c.line(margin, line_y, margin + line_w, line_y)

    c.setFillColorRGB(*faint)
    c.setFont('Helvetica', 6.5)
    c.drawString(
        margin,
        line_y - 11,
        timezone.localtime(when).strftime('%d/%m/%Y · %H:%M'),
    )

    c.showPage()
    c.save()
    return buf.getvalue()


def consolidation_precheck(work_order: WorkOrder) -> dict:
    """Validação rápida para UI — indica se o pedido pode gerar PDF consolidado."""
    attachments = ordered_attachments_for_consolidation(work_order)
    if not attachments:
        return {
            'ok': False,
            'reason': 'no_attachments',
            'message': (
                'Este pedido não possui documentos corrigidos para consolidar. '
                'Adicione os arquivos do novo envio antes de gerar o PDF.'
            ),
        }
    unsupported = [
        att.get_nome_display()
        for att in attachments
        if _attachment_ext(att) in BLOCKED_EXTS
    ]
    if unsupported:
        joined = ', '.join(unsupported)
        return {
            'ok': False,
            'reason': 'unsupported',
            'files': unsupported,
            'message': (
                f'Não é possível incluir no PDF os anexos: {joined}. '
                'Converta-os para PDF ou imagem (JPG/PNG) antes de consolidar.'
            ),
        }
    return {'ok': True, 'count': len(attachments)}


def latest_approval_signature(work_order: WorkOrder):
    return (
        Approval.objects.filter(
            work_order=work_order,
            decisao='aprovado',
        )
        .exclude(signature_data__isnull=True)
        .exclude(signature_data='')
        .select_related('aprovado_por')
        .order_by('-created_at')
        .first()
    )


def try_build_consolidated_approval_email_pdf(work_order: WorkOrder) -> tuple[bytes, str] | None:
    """
    Monta o PDF único (anexos do pedido + página de assinatura) para o e-mail de aprovação.
    Retorna (bytes, nome_arquivo) ou None quando não for possível gerar.
    """
    approval = latest_approval_signature(work_order)
    if not approval or not approval.signature_data:
        logger.info(
            'PDF consolidado não gerado para e-mail do pedido %s: aprovação sem assinatura.',
            work_order.codigo,
        )
        return None

    pre = consolidation_precheck(work_order)
    if not pre.get('ok'):
        logger.warning(
            'PDF consolidado não gerado para e-mail do pedido %s: %s',
            work_order.codigo,
            pre.get('message', 'pré-validação falhou'),
        )
        return None

    try:
        signer = approval.aprovado_por
        signer_name = (signer.get_full_name() or signer.username) if signer else '—'
        pdf_bytes = build_consolidated_signature_pdf(
            work_order=work_order,
            signature_data=approval.signature_data,
            signer_name=signer_name,
            signed_at=approval.created_at,
        )
    except ConsolidationError as exc:
        logger.warning(
            'PDF consolidado não gerado para e-mail do pedido %s: %s',
            work_order.codigo,
            exc,
        )
        return None

    safe_codigo = work_order.codigo.replace('/', '-').replace('\\', '-')
    return pdf_bytes, f'{safe_codigo}_aprovado_consolidado.pdf'


def build_consolidated_signature_pdf(
    *,
    work_order: WorkOrder,
    signature_data: str,
    signer_name: str,
    signed_at=None,
    attachment_order: list[int] | None = None,
) -> bytes:
    attachments = ordered_attachments_for_consolidation(work_order)
    attachments = _reorder_attachments(attachments, attachment_order)
    _validate_attachments(attachments)

    parts: list[bytes] = []
    for att in attachments:
        ext = _attachment_ext(att)
        if ext in BLOCKED_EXTS:
            continue
        if ext not in {PDF_EXT, *IMAGE_EXTS}:
            raise UnsupportedAttachmentsError([att.get_nome_display()])
        parts.append(_pdf_bytes_from_attachment(att))

    parts.append(
        build_signature_page_pdf(
            work_order=work_order,
            signer_name=signer_name,
            signature_data=signature_data,
            signed_at=signed_at,
        )
    )
    return _merge_pdf_parts(parts)
