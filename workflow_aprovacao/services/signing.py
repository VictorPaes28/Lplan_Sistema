from __future__ import annotations

import hashlib
import json
from io import BytesIO
from typing import Any

from django.utils import timezone

from workflow_aprovacao.models import ApprovalHistoryEntry, ApprovalProcess, HistoryAction

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


def _request_ip(request) -> str:
    xff = (request.META.get('HTTP_X_FORWARDED_FOR') or '').strip()
    if xff:
        return xff.split(',')[0].strip()
    return (request.META.get('REMOTE_ADDR') or '').strip()


def build_signature_evidence(*, request, process: ApprovalProcess, action: str, comment: str, signer_name: str) -> dict[str, Any]:
    decided_at = timezone.now()
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
        'user_agent': (request.META.get('HTTP_USER_AGENT') or '')[:500],
    }
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    return {
        'evidence_version': 1,
        'signature_hash_sha256': digest,
        'signed_snapshot': snapshot,
    }


def latest_final_signature_event(process: ApprovalProcess) -> ApprovalHistoryEntry | None:
    return (
        process.history_entries.filter(
            action__in=(HistoryAction.APPROVED_STEP, HistoryAction.REJECTED),
            new_status__in=('approved', 'rejected'),
        )
        .select_related('actor')
        .order_by('-created_at')
        .first()
    )


def render_signature_receipt_pdf(*, process: ApprovalProcess, event: ApprovalHistoryEntry) -> bytes:
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError('ReportLab não disponível para gerar comprovante PDF.')

    payload = event.payload or {}
    evidence = payload.get('signature_evidence') or {}
    hash_value = evidence.get('signature_hash_sha256', '')
    snap = evidence.get('signed_snapshot') or {}

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50
    c.setFont('Helvetica-Bold', 14)
    c.drawString(40, y, 'Comprovante de Assinatura Eletrónica')
    y -= 26
    c.setFont('Helvetica', 10)
    lines = [
        f'Processo: #{process.pk}',
        f'Obra: {process.project.code} - {process.project.name}',
        f'Categoria: {process.category.name}',
        f'Decisao final: {process.get_status_display()}',
        f'Signatario: {snap.get("signer_name") or "-"}',
        f'Utilizador: {(event.actor.get_full_name() or event.actor.username) if event.actor else "-"}',
        f'Data/hora: {event.created_at.strftime("%d/%m/%Y %H:%M:%S")}',
        f'IP: {snap.get("ip") or "-"}',
        f'User-Agent: {(snap.get("user_agent") or "-")[:95]}',
        f'Hash SHA-256: {hash_value or "-"}',
    ]
    for line in lines:
        c.drawString(40, y, line)
        y -= 16

    y -= 10
    c.setFont('Helvetica-Bold', 10)
    c.drawString(40, y, 'Termo de confirmação')
    y -= 15
    c.setFont('Helvetica', 9)
    c.drawString(
        40,
        y,
        'Este comprovante regista trilha de auditoria da assinatura realizada no fluxo de aprovação.',
    )
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()
