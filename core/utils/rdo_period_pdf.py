"""
PDF consolidado de vários RDOs (Diário de Obra) em um intervalo de datas.

Texto-only (sem fotos/anexos) para manter o arquivo leve; fotos seguem nos PDFs individuais de cada dia.
"""
from __future__ import annotations

import logging
from datetime import date
from io import BytesIO
from typing import Any

from django.utils import timezone

from core.utils.pdf_generator import REPORTLAB_AVAILABLE, _safe_pdf_multiline_text, _safe_pdf_text

logger = logging.getLogger(__name__)

_MAX_FIELD = 6000


def _clip(text: str, max_len: int = _MAX_FIELD) -> str:
    t = (text or "").strip()
    if len(t) > max_len:
        return t[: max_len - 3] + "..."
    return t


def generate_rdo_period_pdf_bytes(project, date_from: date, date_to: date) -> BytesIO | None:
    """
    Gera PDF com um capítulo por dia que possua ConstructionDiary no intervalo [date_from, date_to].
    Retorna BytesIO ou None se ReportLab indisponível ou sem diários.
    """
    if not REPORTLAB_AVAILABLE:
        logger.warning("ReportLab indisponível — PDF consolidado não gerado.")
        return None

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    from core.models import ConstructionDiary

    qs = (
        ConstructionDiary.objects.filter(project=project, date__gte=date_from, date__lte=date_to)
        .select_related("project", "created_by", "reviewed_by")
        .prefetch_related(
            "work_logs__activity",
            "occurrences",
        )
        .order_by("date", "id")
    )
    diaries = list(qs)
    if not diaries:
        return None

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="PeriodTitle",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=8,
    )
    day_title = ParagraphStyle(
        name="DayTitle",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body = ParagraphStyle(
        name="PeriodBody",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155"),
    )
    label_style = ParagraphStyle(
        name="Lbl",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#64748b"),
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=f"RDO consolidado {project.code}",
    )
    story: list[Any] = []

    gen_em = timezone.now().strftime("%d/%m/%Y %H:%M")
    story.append(Paragraph(_safe_pdf_text(f"Relatório consolidado — RDO / Diário de Obra"), title_style))
    story.append(Paragraph(_safe_pdf_text(f"Obra: {project.code} — {project.name}"), body))
    story.append(
        Paragraph(
            _safe_pdf_multiline_text(
                f"Período: {date_from.strftime('%d/%m/%Y')} a {date_to.strftime('%d/%m/%Y')} "
                f"({len(diaries)} dia(s) com registro). Gerado em {gen_em}. "
                "Fotos, vídeos e anexos não são incluídos — consulte o PDF de cada dia no sistema."
            ),
            body,
        )
    )
    story.append(Spacer(1, 8))

    for idx, diary in enumerate(diaries):
        if idx:
            story.append(PageBreak())
        dlabel = diary.date.strftime("%d/%m/%Y") if diary.date else "-"
        rno = diary.report_number or "-"
        st = diary.get_status_display() if hasattr(diary, "get_status_display") else str(diary.status)
        story.append(Paragraph(_safe_pdf_text(f"{dlabel} · RDO nº {rno} · {st}"), day_title))

        def add_block(label: str, value: str):
            v = _clip(value)
            if not v:
                return
            story.append(Paragraph(f"<b>{_safe_pdf_text(label)}</b>", label_style))
            story.append(Paragraph(_safe_pdf_multiline_text(v), body))
            story.append(Spacer(1, 4))

        add_block("Responsável inspeção", diary.inspection_responsible or "")
        add_block("Responsável produção", diary.production_responsible or "")
        add_block("Condições climáticas", diary.weather_conditions or "")
        if diary.work_hours is not None:
            story.append(Paragraph(_safe_pdf_text(f"<b>Horas trabalhadas:</b> {diary.work_hours}"), body))
            story.append(Spacer(1, 4))
        add_block("Deliberações", diary.deliberations or "")
        add_block("Observações gerais", diary.general_notes or "")
        add_block("Acidentes", diary.accidents or "")
        add_block("Paralisações", diary.stoppages or "")
        add_block("Riscos eminentes", diary.imminent_risks or "")
        add_block("Outros incidentes", diary.incidents or "")
        add_block("Fiscalizações", diary.inspections or "")
        add_block("DDS", diary.dds or "")

        ocs = list(diary.occurrences.all()[:50])
        if ocs:
            story.append(Paragraph(_safe_pdf_text("<b>Ocorrências</b>"), label_style))
            for oc in ocs:
                desc = _clip(oc.description or "", 2000)
                if desc:
                    story.append(Paragraph(_safe_pdf_multiline_text(f"• {desc}"), body))
            story.append(Spacer(1, 4))

        logs = list(diary.work_logs.select_related("activity").all())
        if logs:
            story.append(Paragraph(_safe_pdf_text("<b>Atividades / EAP (registro do dia)</b>"), label_style))
            for wl in logs:
                act = wl.activity
                an = act.display_code_name if act else "-"
                pct = wl.percentage_executed_today
                loc = (wl.location or "").strip()
                nt = _clip(wl.notes or "", 1500)
                line = f"• {an} — {pct}% executado no dia"
                if loc:
                    line += f" — Local: {loc}"
                story.append(Paragraph(_safe_pdf_multiline_text(line), body))
                if nt:
                    story.append(Paragraph(_safe_pdf_multiline_text(nt), body))
            story.append(Spacer(1, 4))

        criador = ""
        if diary.created_by:
            criador = diary.created_by.get_full_name() or diary.created_by.username
        if criador:
            story.append(Paragraph(_safe_pdf_text(f"Preenchido por: {criador}"), label_style))

    doc.build(story)
    buf.seek(0)
    return buf
