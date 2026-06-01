from __future__ import annotations

import hashlib
import json
import os
import re
from io import BytesIO
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

from workflow_aprovacao.models import (
    ApprovalHistoryEntry,
    ApprovalProcess,
    HistoryAction,
    ProcessStatus,
)

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False
    cm = None  # type: ignore[assignment,misc]
    ImageReader = None  # type: ignore[assignment,misc]

_MARGIN_X = 48
_LINE = 15
_SECTION_GAP = 22
_COLOR_PRIMARY = (26 / 255, 58 / 255, 92 / 255)  # #1A3A5C
_COLOR_HEADER_BG = (234 / 255, 242 / 255, 251 / 255)  # #EAF2FB
_COLOR_BORDER = (208 / 255, 217 / 255, 227 / 255)  # #D0D9E3


def logo_path_for_receipt_pdf() -> str | None:
    """Mesma resolução de logo dos PDFs do Diário / GestControll."""
    try:
        from core.utils.pdf_generator import _get_logo_absolute_path

        path = _get_logo_absolute_path()
        if path and os.path.exists(path):
            return path
    except Exception:
        pass
    logo_dir = Path(settings.BASE_DIR) / 'core' / 'static' / 'core' / 'images'
    for name in (
        'lpla-logo-pdf-transparent.png',
        'lpla-logo-pdf.png',
        'lplan-logo2.png',
        'lplan_logo.png',
        'lplan_logo.jpg',
        'lplan_logo.jpeg',
    ):
        candidate = logo_dir / name
        if candidate.exists():
            return str(candidate)
    return None


def _scaled_logo_size(logo_path: str) -> tuple[float, float]:
    max_logo_w = 4.8 * cm
    max_logo_h = 1.15 * cm
    logo_w, logo_h = max_logo_w, max_logo_h
    try:
        src_w, src_h = ImageReader(logo_path).getSize()
        if src_w and src_h:
            scale = min(max_logo_w / float(src_w), max_logo_h / float(src_h))
            logo_w = max(1.0 * cm, float(src_w) * scale)
            logo_h = max(0.4 * cm, float(src_h) * scale)
    except Exception:
        pass
    return logo_w, logo_h


def _request_ip(request) -> str:
    xff = (request.META.get('HTTP_X_FORWARDED_FOR') or '').strip()
    if xff:
        return xff.split(',')[0].strip()
    return (request.META.get('REMOTE_ADDR') or '').strip()


def _parse_geolocation_data(raw: str) -> dict[str, Any]:
    raw = (raw or '').strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}

    lat = parsed.get('latitude')
    lng = parsed.get('longitude')
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return {}
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return {}

    geo: dict[str, Any] = {
        'latitude': round(lat, 6),
        'longitude': round(lng, 6),
        'source': (parsed.get('source') or 'browser').strip()[:32],
    }
    try:
        accuracy = float(parsed.get('accuracy_m'))
        if accuracy > 0:
            geo['accuracy_m'] = round(accuracy, 1)
    except (TypeError, ValueError):
        pass
    captured_at = (parsed.get('captured_at') or '').strip()
    if captured_at:
        geo['captured_at'] = captured_at[:40]
    address = (parsed.get('address') or '').strip()
    if address:
        geo['address'] = address[:240]
    maps_url = (parsed.get('maps_url') or '').strip()
    if maps_url:
        geo['maps_url'] = maps_url[:500]
    return geo


def _format_geolocation_label(geo: dict[str, Any]) -> str:
    if not geo:
        return ''
    acc = geo.get('accuracy_m')
    acc_suffix = f' (precisão ~{acc} m)' if acc is not None else ''
    address = (geo.get('address') or '').strip()
    if address:
        return f'{address}{acc_suffix}'
    lat = geo.get('latitude')
    lng = geo.get('longitude')
    if lat is None or lng is None:
        return ''
    return f'{lat:.6f}, {lng:.6f}{acc_suffix}'


def geolocation_display_from_geo(geo: dict[str, Any]) -> dict[str, str]:
    if not geo:
        return {}
    lat = geo.get('latitude')
    lng = geo.get('longitude')
    coords = ''
    maps_url = (geo.get('maps_url') or '').strip()
    if lat is not None and lng is not None:
        try:
            lat_f = float(lat)
            lng_f = float(lng)
            coords = f'{lat_f:.6f}, {lng_f:.6f}'
            if not maps_url:
                from workflow_aprovacao.services.geocoding import google_maps_url

                maps_url = google_maps_url(latitude=lat_f, longitude=lng_f)
        except (TypeError, ValueError):
            pass
    label = _format_geolocation_label(geo)
    if not label:
        return {}
    address = (geo.get('address') or '').strip()
    return {
        'label': label,
        'address': address,
        'coords': coords,
        'maps_url': maps_url,
    }


def build_signature_evidence(
    *,
    request,
    process: ApprovalProcess,
    action: str,
    comment: str,
    signer_name: str,
    signature_data: str = '',
    geolocation_data: str = '',
) -> dict[str, Any]:
    decided_at = timezone.now()
    sig = (signature_data or '').strip()
    has_manual = sig.startswith('data:image/png;base64,') and len(sig) > 500
    geolocation = _parse_geolocation_data(geolocation_data)
    if geolocation:
        from workflow_aprovacao.services.geocoding import enrich_geolocation

        geolocation = enrich_geolocation(geolocation)
    geolocation_label = _format_geolocation_label(geolocation)
    snapshot = {
        'process_id': process.pk,
        'project_code': process.project.code,
        'category_code': process.category.code,
        'status_before': process.status,
        'current_step_sequence': process.current_step.sequence if process.current_step else None,
        'current_step_name': process.current_step.name if process.current_step else '',
        'external_system': process.external_system,
        'external_entity_type': process.external_entity_type,
        'external_id': process.external_id,
        'title': process.title,
        'summary': process.summary,
        'external_payload': process.external_payload or {},
        'decision_action': action,
        'decision_comment': comment,
        'signer_name': signer_name,
        'signer_user_id': getattr(request.user, 'pk', None),
        'decided_at': decided_at.isoformat(),
        'ip': _request_ip(request),
        'geo_location': geolocation,
        'geo_label': geolocation_label,
        'user_agent': (request.META.get('HTTP_USER_AGENT') or '')[:500],
        'has_manual_signature': has_manual,
    }
    if has_manual:
        snapshot['signature_image_sha256'] = hashlib.sha256(sig.encode('utf-8')).hexdigest()
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    return {
        'evidence_version': 2,
        'signature_hash_sha256': digest,
        'signed_snapshot': snapshot,
        'signature_image_png': sig if has_manual else '',
    }


def latest_final_signature_event(process: ApprovalProcess) -> ApprovalHistoryEntry | None:
    return (
        process.history_entries.filter(
            action__in=(HistoryAction.APPROVED_STEP, HistoryAction.REJECTED),
            new_status__in=(ProcessStatus.APPROVED, ProcessStatus.REJECTED),
        )
        .select_related('actor', 'step')
        .order_by('-created_at')
        .first()
    )


def _actor_label(entry: ApprovalHistoryEntry) -> str:
    if not entry.actor:
        return '—'
    return (entry.actor.get_full_name() or '').strip() or entry.actor.username


def _decision_heading(event: ApprovalHistoryEntry, process: ApprovalProcess) -> str:
    if event.action == HistoryAction.REJECTED:
        return 'Reprovação do fluxo'
    if process.status == ProcessStatus.APPROVED:
        return 'Aprovação — fluxo concluído'
    return event.get_action_display()


_HISTORY_IN_RECEIPT = frozenset(
    {
        HistoryAction.SUBMITTED,
        HistoryAction.APPROVED_STEP,
        HistoryAction.REJECTED,
        HistoryAction.CANCELLED,
    }
)


def _history_event_summary(entry: ApprovalHistoryEntry) -> str:
    if entry.action == HistoryAction.SUBMITTED:
        return 'Processo iniciado'
    if entry.action == HistoryAction.APPROVED_STEP:
        if entry.new_status == ProcessStatus.APPROVED:
            return 'Aprovação — fluxo concluído'
        if entry.new_status == ProcessStatus.AWAITING_STEP:
            return 'Aprovação — encaminhado à próxima alçada'
        return 'Aprovado na alçada'
    if entry.action == HistoryAction.REJECTED:
        return 'Reprovação do fluxo'
    if entry.action == HistoryAction.CANCELLED:
        return 'Processo cancelado'
    return entry.get_action_display()


def _history_step_label(entry: ApprovalHistoryEntry) -> str:
    seq = entry.step_sequence_snapshot
    name = ''
    if entry.step_id and entry.step:
        name = (entry.step.name or '').strip()
    if seq and name:
        return f'Alçada {seq}: {name}'
    if seq:
        return f'Alçada {seq}'
    if name:
        return name
    return ''


_LEGACY_GEO_LABEL_RE = re.compile(
    r'Lat\s+([-\d.]+)\s*,\s*Lon\s+([-\d.]+)',
    re.IGNORECASE,
)


def _coords_from_legacy_geo_label(label: str) -> tuple[float, float] | None:
    match = _LEGACY_GEO_LABEL_RE.search(label or '')
    if not match:
        return None
    try:
        lat = float(match.group(1))
        lng = float(match.group(2))
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return lat, lng


def history_geolocation_label(entry: ApprovalHistoryEntry) -> str:
    display = history_geolocation_display(entry)
    return display.get('label', '')


def _history_geolocation_raw(entry: ApprovalHistoryEntry) -> dict[str, Any]:
    payload = entry.payload or {}
    evidence = payload.get('signature_evidence') or {}
    if not evidence:
        return {}
    snap = evidence.get('signed_snapshot') or {}
    geo = snap.get('geo_location') or {}
    if isinstance(geo, dict) and geo:
        return geo
    return {}


def history_geolocation_display(entry: ApprovalHistoryEntry) -> dict[str, str]:
    geo = _history_geolocation_raw(entry)
    if geo:
        return geolocation_display_from_geo(geo)
    payload = entry.payload or {}
    evidence = payload.get('signature_evidence') or {}
    snap = evidence.get('signed_snapshot') or {}
    label = (snap.get('geo_label') or '').strip()
    if not label:
        return {}
    coords = ''
    maps_url = ''
    parsed = _coords_from_legacy_geo_label(label)
    if parsed:
        from workflow_aprovacao.services.geocoding import google_maps_url

        lat, lng = parsed
        coords = f'{lat:.6f}, {lng:.6f}'
        maps_url = google_maps_url(latitude=lat, longitude=lng)
    return {'label': label, 'address': '', 'coords': coords, 'maps_url': maps_url}


def build_final_signature_audit(
    event: ApprovalHistoryEntry | None,
) -> dict[str, Any] | None:
    if not event:
        return None
    payload = event.payload or {}
    evidence = payload.get('signature_evidence') or {}
    snap = evidence.get('signed_snapshot') or {}
    digest = (evidence.get('signature_hash_sha256') or '').strip()
    geo_label = history_geolocation_label(event)
    geo_display = history_geolocation_display(event)
    if not digest and not geo_label:
        return None
    signer = (snap.get('signer_name') or '').strip()
    actor = _actor_label(event)
    return {
        'actor': actor,
        'signer_name': signer if signer and signer.lower() != actor.lower() else '',
        'signed_by': signer or actor,
        'geo_label': geo_label,
        'geo_maps_url': geo_display.get('maps_url', ''),
        'geo_coords': geo_display.get('coords', ''),
        'decided_at': event.created_at,
        'action_display': event.get_action_display(),
        'hash_short': digest[:16] if digest else '',
    }


def _history_signature_note(entry: ApprovalHistoryEntry) -> str:
    payload = entry.payload or {}
    evidence = payload.get('signature_evidence') or {}
    digest = (evidence.get('signature_hash_sha256') or '').strip()
    if not digest:
        return ''
    snap = evidence.get('signed_snapshot') or {}
    signer = (snap.get('signer_name') or '').strip()
    parts = [f'Código: {digest[:16]}…']
    if signer:
        parts.append(f'nome declarado: {signer}')
    return ' · '.join(parts)


def process_history_for_receipt(process: ApprovalProcess) -> list[ApprovalHistoryEntry]:
    return list(
        process.history_entries.filter(action__in=_HISTORY_IN_RECEIPT)
        .select_related('actor', 'step')
        .order_by('created_at', 'pk')
    )


def _step_label(event: ApprovalHistoryEntry, snap: dict) -> str:
    seq = event.step_sequence_snapshot or snap.get('current_step_sequence')
    name = ''
    if event.step_id and event.step:
        name = (event.step.name or '').strip()
    if not name:
        name = (snap.get('current_step_name') or '').strip()
    if seq and name:
        return f'Alçada {seq}: {name}'
    if seq:
        return f'Alçada {seq}'
    if name:
        return name
    return '—'


def _pdf_writer(c: canvas.Canvas, *, logo_path: str | None = None) -> '_ReceiptLayout':
    return _ReceiptLayout(c, logo_path=logo_path)


class _ReceiptLayout:
    def __init__(self, c: canvas.Canvas, *, logo_path: str | None = None) -> None:
        self.c = c
        self.width, self.height = A4
        self.logo_path = logo_path if logo_path and os.path.exists(logo_path) else None
        self.y = self.height - 52
        self._header_drawn = False

    def _ensure_space(self, needed: float) -> None:
        if self.y - needed < 56:
            self.c.showPage()
            self.y = self.height - 52

    def title(self, text: str, *, subtitle: str = 'Central de Aprovações') -> None:
        if self._header_drawn:
            return
        self._header_drawn = True
        self.y = self._draw_institutional_header(text, subtitle)

    def _draw_institutional_header(self, title: str, subtitle: str) -> float:
        """Cabeçalho alinhado ao RDO: faixa #EAF2FB, logo à esquerda, título centralizado."""
        pad_top = 28
        pad_inner = 10
        box_left = _MARGIN_X - 8
        box_right = self.width - _MARGIN_X + 8
        box_width = box_right - box_left

        logo_w = logo_h = 0.0
        if self.logo_path:
            logo_w, logo_h = _scaled_logo_size(self.logo_path)

        title_block_h = 30
        inner_h = max(logo_h, title_block_h) + pad_inner
        box_top = self.height - pad_top
        box_bottom = box_top - inner_h - pad_inner

        self.c.setFillColorRGB(*_COLOR_HEADER_BG)
        self.c.rect(box_left, box_bottom, box_width, box_top - box_bottom, fill=1, stroke=0)
        self.c.setFillColorRGB(0, 0, 0)

        if self.logo_path and logo_h:
            logo_y = box_bottom + (box_top - box_bottom - logo_h) / 2
            self.c.drawImage(
                self.logo_path,
                _MARGIN_X,
                logo_y,
                width=logo_w,
                height=logo_h,
                preserveAspectRatio=True,
                mask='auto',
            )

        title_y = box_top - 20
        self.c.setFont('Helvetica-Bold', 14)
        self.c.setFillColorRGB(*_COLOR_PRIMARY)
        self.c.drawCentredString(self.width / 2, title_y, title)
        self.c.setFont('Helvetica', 9)
        self.c.drawCentredString(self.width / 2, title_y - 14, subtitle)
        self.c.setFillColorRGB(0, 0, 0)

        line_y = box_bottom - 5
        self.c.setStrokeColorRGB(*_COLOR_BORDER)
        self.c.line(box_left, line_y, box_right, line_y)
        self.c.setStrokeColorRGB(0, 0, 0)
        return line_y - _SECTION_GAP

    def section(self, title: str) -> None:
        self._ensure_space(40)
        self.c.setFont('Helvetica-Bold', 11)
        self.c.drawString(_MARGIN_X, self.y, title)
        self.y -= 4
        self.c.setStrokeColorRGB(0.82, 0.85, 0.9)
        self.c.line(_MARGIN_X, self.y, self.width - _MARGIN_X, self.y)
        self.c.setStrokeColorRGB(0, 0, 0)
        self.y -= 14

    def row(self, label: str, value: str, *, bold_value: bool = False) -> None:
        value = (value or '—').strip() or '—'
        self._ensure_space(_LINE + 4)
        self.c.setFont('Helvetica', 9)
        self.c.setFillColorRGB(0.4, 0.45, 0.5)
        self.c.drawString(_MARGIN_X, self.y, label)
        self.c.setFillColorRGB(0, 0, 0)
        self.c.setFont('Helvetica-Bold' if bold_value else 'Helvetica', 10)
        max_w = self.width - _MARGIN_X - 130
        if self.c.stringWidth(value, 'Helvetica-Bold' if bold_value else 'Helvetica', 10) <= max_w:
            self.c.drawString(_MARGIN_X + 118, self.y, value)
            self.y -= _LINE
            return
        self.y -= _LINE
        for chunk in _wrap_text(value, max_w, self.c, 'Helvetica-Bold' if bold_value else 'Helvetica', 10):
            self._ensure_space(_LINE)
            self.c.drawString(_MARGIN_X + 118, self.y, chunk)
            self.y -= _LINE

    def paragraph(self, text: str, *, size: int = 9) -> None:
        text = (text or '').strip()
        if not text:
            return
        max_w = self.width - 2 * _MARGIN_X
        for line in _wrap_text(text, max_w, self.c, 'Helvetica', size):
            self._ensure_space(_LINE)
            self.c.setFont('Helvetica', size)
            self.c.drawString(_MARGIN_X, self.y, line)
            self.y -= _LINE

    def gap(self, px: float = 10) -> None:
        self.y -= px

    def timeline_entry(
        self,
        index: int,
        entry: ApprovalHistoryEntry,
        *,
        highlight: bool = False,
        include_geolocation: bool = False,
    ) -> None:
        when = timezone.localtime(entry.created_at).strftime('%d/%m/%Y %H:%M:%S')
        summary = _history_event_summary(entry)
        if highlight:
            summary = f'{summary} (decisão final)'
        step_txt = _history_step_label(entry)
        actor = _actor_label(entry)
        comment = (entry.comment or '').strip()
        sig_note = _history_signature_note(entry)
        geo_label = history_geolocation_label(entry) if include_geolocation else ''

        self._ensure_space(48)

        self.c.setFont('Helvetica-Bold', 9)
        self.c.setFillColorRGB(0.35, 0.4, 0.5)
        self.c.drawString(_MARGIN_X, self.y, f'{index}.')
        self.c.setFillColorRGB(0, 0, 0)
        self.c.drawString(_MARGIN_X + 16, self.y, when)
        self.y -= 13

        self.c.setFont('Helvetica-Bold', 10)
        self.c.drawString(_MARGIN_X + 16, self.y, summary)
        self.y -= 13

        if step_txt:
            self.c.setFont('Helvetica', 9)
            self.c.setFillColorRGB(0.25, 0.28, 0.35)
            self.c.drawString(_MARGIN_X + 16, self.y, step_txt)
            self.c.setFillColorRGB(0, 0, 0)
            self.y -= 12

        self.c.setFont('Helvetica', 9)
        self.c.drawString(_MARGIN_X + 16, self.y, f'Por: {actor}')
        self.y -= 12

        if comment:
            max_w = self.width - _MARGIN_X - 32
            self.c.setFillColorRGB(0.35, 0.38, 0.45)
            for line in _wrap_text(f'Obs.: {comment}', max_w, self.c, 'Helvetica', 9):
                self.c.drawString(_MARGIN_X + 16, self.y, line)
                self.y -= 11
            self.c.setFillColorRGB(0, 0, 0)

        if geo_label:
            self.c.setFont('Helvetica', 8)
            self.c.setFillColorRGB(0.45, 0.48, 0.55)
            self.c.drawString(_MARGIN_X + 16, self.y, f'Localização: {geo_label}')
            self.c.setFillColorRGB(0, 0, 0)
            self.y -= 11

        if sig_note:
            self.c.setFont('Helvetica', 8)
            self.c.setFillColorRGB(0.45, 0.48, 0.55)
            self.c.drawString(_MARGIN_X + 16, self.y, sig_note)
            self.c.setFillColorRGB(0, 0, 0)
            self.y -= 11

        self.y -= 6

    def signature_image(self, data_url: str) -> bool:
        if not data_url.startswith('data:image/png;base64,'):
            return False
        try:
            import base64

            from reportlab.lib.utils import ImageReader

            raw = base64.b64decode(data_url.split(',', 1)[1])
            img = ImageReader(BytesIO(raw))
            iw, ih = img.getSize()
            max_w, max_h = 240, 80
            scale = min(max_w / iw, max_h / ih, 1.0)
            w, h = iw * scale, ih * scale
            self._ensure_space(h + 24)
            self.c.setFont('Helvetica', 9)
            self.c.setFillColorRGB(0.4, 0.45, 0.5)
            self.c.drawString(_MARGIN_X, self.y, 'Desenho da assinatura')
            self.c.setFillColorRGB(0, 0, 0)
            self.y -= 8
            self.c.drawImage(img, _MARGIN_X, self.y - h, width=w, height=h, mask='auto')
            self.y -= h + 12
            return True
        except Exception:
            return False

    def footer_note(self, text: str) -> None:
        self.gap(8)
        self._ensure_space(30)
        self.c.setFont('Helvetica', 8)
        self.c.setFillColorRGB(0.45, 0.48, 0.55)
        for line in _wrap_text(text, self.width - 2 * _MARGIN_X, self.c, 'Helvetica', 8):
            self.c.drawString(_MARGIN_X, self.y, line)
            self.y -= 11
        self.c.setFillColorRGB(0, 0, 0)


def _wrap_text(text: str, max_width: float, c: canvas.Canvas, font: str, size: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f'{current} {word}'
        if c.stringWidth(trial, font, size) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def render_signature_receipt_pdf(
    *,
    process: ApprovalProcess,
    event: ApprovalHistoryEntry,
    include_geolocation: bool = False,
) -> bytes:
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError('ReportLab não disponível para gerar comprovante PDF.')

    payload = event.payload or {}
    evidence = payload.get('signature_evidence') or {}
    hash_value = evidence.get('signature_hash_sha256', '')
    snap = evidence.get('signed_snapshot') or {}

    history = process_history_for_receipt(process)
    if not history:
        history = [event]

    started = history[0].created_at if history else event.created_at
    finished = event.created_at

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    doc = _pdf_writer(c, logo_path=logo_path_for_receipt_pdf())

    doc.title('Comprovante de assinatura')

    doc.section('Processo')
    doc.row('Número', f'#{process.pk}', bold_value=True)
    doc.row('Categoria', process.category.name)
    doc.row('Obra', f'{process.project.code} — {process.project.name}')
    if (process.title or '').strip():
        doc.row('Referência', process.title.strip())
    doc.row('Situação final', process.get_status_display(), bold_value=True)
    doc.row(
        'Período',
        f'{timezone.localtime(started).strftime("%d/%m/%Y %H:%M")} — '
        f'{timezone.localtime(finished).strftime("%d/%m/%Y %H:%M")}',
    )

    doc.gap(6)
    doc.section('Histórico do fluxo')
    for i, entry in enumerate(history, start=1):
        doc.timeline_entry(
            i,
            entry,
            highlight=(entry.pk == event.pk),
            include_geolocation=include_geolocation,
        )

    doc.gap(6)
    doc.section('Assinatura da decisão final')
    signer = (snap.get('signer_name') or '').strip()
    actor = _actor_label(event)
    if signer and signer.lower() != actor.lower():
        doc.row('Nome declarado', signer)
        doc.row('Conta no sistema', actor)
    else:
        doc.row('Assinado por', signer or actor, bold_value=True)

    final_comment = (event.comment or snap.get('decision_comment') or '').strip()
    if final_comment:
        doc.row('Comentário', final_comment)

    sig_png = evidence.get('signature_image_png') or ''
    has_img = doc.signature_image(sig_png)
    if not has_img and snap.get('has_manual_signature'):
        doc.gap(4)
        doc.paragraph('Assinatura manual registrada (imagem indisponível neste comprovante).', size=9)

    doc.gap(8)
    doc.section('Registro de auditoria (decisão final)')
    doc.row('Código de verificação', hash_value or '—')
    if include_geolocation:
        geo_location = snap.get('geo_location') or {}
        geo_display = (
            geolocation_display_from_geo(geo_location)
            if isinstance(geo_location, dict)
            else {}
        )
        doc.row('Localização', snap.get('geo_label') or geo_display.get('label') or 'Não informada')
        if geo_display.get('maps_url'):
            doc.row('Abrir no Maps', geo_display['maps_url'])
    doc.row('Endereço IP (rede)', snap.get('ip') or '—')
    ua = (snap.get('user_agent') or '').strip()
    if ua:
        doc.gap(2)
        doc.paragraph(f'Navegador: {ua}', size=8)

    doc.footer_note(
        'Documento gerado automaticamente pela Central de Aprovações. '
        'O histórico lista todas as etapas registradas; o código de verificação refere-se à assinatura da decisão final.'
    )

    c.save()
    buffer.seek(0)
    return buffer.getvalue()
