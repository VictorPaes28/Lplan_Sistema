"""
PDF da listagem de restrições (ReportLab), alinhado ao padrão visual GestControll/Diário.
"""
import io
import os
from xml.sax.saxutils import escape as xml_escape

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _pdf_esc(text):
    return xml_escape(str(text if text is not None else ""), {'"': "&quot;", "'": "&#39;"})


def _logo_path():
    logo_dir = os.path.join(settings.BASE_DIR, "core", "static", "core", "images")
    for name in (
        "lpla-logo-pdf-transparent.png",
        "lpla-logo-pdf.png",
        "lplan-logo2.png",
        "lplan_logo.png",
        "lplan_logo.jpg",
        "lplan_logo.jpeg",
    ):
        p = os.path.join(logo_dir, name)
        if os.path.exists(p):
            return p
    return None


def _clip(v, n=120):
    txt = str(v or "").strip()
    if len(txt) <= n:
        return txt or "—"
    return txt[: max(0, n - 3)] + "..."


def build_impedimentos_list_pdf_bytes(
    *,
    obra_nome: str,
    obra_sigla: str,
    project_code: str,
    metadata_lines: list[str],
    items: list[dict],
    total_count: int,
    exported_count: int,
    max_rows: int,
    lista_finalizado_status_id: int | None = None,
) -> bytes:
    color_primary = colors.HexColor("#1A3A5C")
    color_accent = colors.HexColor("#E8F0F8")
    color_border = colors.HexColor("#D0D9E3")
    color_text = colors.HexColor("#1C1C1C")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2.0 * cm,
        leftMargin=2.0 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
    )
    styles = getSampleStyleSheet()
    content_width = doc.width
    report_width = max(content_width - (0.3 * cm), 12 * cm)

    normal = ParagraphStyle(
        "ImpPdfNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        textColor=color_text,
        leading=9,
    )
    th = ParagraphStyle(
        "ImpPdfTH",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    title_style = ParagraphStyle(
        "ImpPdfTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=color_primary,
        alignment=TA_CENTER,
    )
    sub_style = ParagraphStyle(
        "ImpPdfSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=color_primary,
        alignment=TA_CENTER,
    )

    titulo_obra = obra_nome or "—"
    if obra_sigla:
        titulo_obra = f"{titulo_obra} ({obra_sigla})"
    if project_code:
        titulo_obra = f"{titulo_obra} · {project_code}"

    title_main = Paragraph(
        "<font color='#1A3A5C'><b>RESTRIÇÕES</b></font>", title_style
    )
    meta_html = "<font size='8' color='#1A3A5C'>" + " · ".join(
        _pdf_esc(line) for line in metadata_lines
    ) + "</font>"
    title_sub = Paragraph(meta_html, sub_style)

    story = []
    lp = _logo_path()
    if lp:
        from reportlab.platypus import Image as RLImage

        logo_col_w = min(4.8 * cm, report_width * 0.30)
        text_col_w = max(report_width - logo_col_w, 8 * cm)
        logo = RLImage(lp, width=4.4 * cm, height=1.05 * cm)
        text_block = Table([[title_main], [title_sub]], colWidths=[text_col_w])
        text_block.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        hdr = Table([[logo, text_block]], colWidths=[logo_col_w, text_col_w], hAlign="CENTER")
    else:
        hdr = Table([[title_main], [title_sub]], colWidths=[report_width], hAlign="CENTER")
    hdr.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, -1), (-1, -1), 0.7, color_primary),
            ]
        )
    )
    story.append(hdr)
    story.append(Spacer(1, 0.35 * cm))

    obra_line = Paragraph(
        f"<b>{_pdf_esc(titulo_obra)}</b>",
        ParagraphStyle(
            "ImpObraLine",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            textColor=color_primary,
            alignment=TA_LEFT,
            spaceAfter=6,
        ),
    )
    story.append(obra_line)

    section_title = ParagraphStyle(
        "ImpPdfSection",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.3,
        textColor=color_primary,
        spaceBefore=2,
        spaceAfter=4,
    )
    story.append(Paragraph("LISTAGEM", section_title))

    detail_rows = []
    for item in items:
        responsaveis = item.get("responsaveis") or []
        resp_txt = ", ".join(r.get("nome", "") for r in responsaveis if r.get("nome"))
        if not resp_txt.strip():
            resp_txt = "—"
        prazo = item.get("prazo")
        prazo_txt = prazo.strftime("%d/%m/%Y") if prazo else "—"
        criado = item.get("criado_em")
        if criado:
            criado_txt = timezone.localtime(criado).strftime("%d/%m/%Y %H:%M")
        else:
            criado_txt = "—"
        ultima_conclusao = item.get("ultima_conclusao_em")
        is_concluido = (
            lista_finalizado_status_id is not None
            and item.get("status_id") == lista_finalizado_status_id
        )
        if is_concluido and ultima_conclusao:
            fin_txt = timezone.localtime(ultima_conclusao).strftime("%d/%m/%Y %H:%M")
        else:
            fin_txt = "—"
        detail_rows.append(
            [
                Paragraph(_pdf_esc(_clip(item.get("titulo"), 200)), normal),
                Paragraph(_pdf_esc(_clip(item.get("status_nome"), 40)), normal),
                Paragraph(_pdf_esc(_clip(item.get("prioridade"), 24)), normal),
                Paragraph(_pdf_esc(_clip(resp_txt, 160)), normal),
                Paragraph(_pdf_esc(prazo_txt), normal),
                Paragraph(_pdf_esc(criado_txt), normal),
                Paragraph(_pdf_esc(fin_txt), normal),
            ]
        )

    data_rows = [
        [
            Paragraph("Título", th),
            Paragraph("Status", th),
            Paragraph("Prioridade", th),
            Paragraph("Responsáveis", th),
            Paragraph("Prazo", th),
            Paragraph("Criado em", th),
            Paragraph("Finalizado em", th),
        ]
    ] + detail_rows

    detail_fracs = [0.23, 0.12, 0.11, 0.19, 0.09, 0.13, 0.13]
    detail_col_widths = [report_width * f for f in detail_fracs]
    tbl = LongTable(
        data_rows,
        colWidths=detail_col_widths,
        repeatRows=1,
        hAlign="CENTER",
    )
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), color_primary),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, color_border),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, color_accent]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ]
        )
    )
    story.append(tbl)
    if total_count > max_rows:
        story.append(Spacer(1, 0.2 * cm))
        trunc_msg = (
            f"Lista truncada: {total_count} restrições no filtro; "
            f"exportados os primeiros {max_rows}."
        )
        story.append(
            Paragraph(
                f"<i>{_pdf_esc(trunc_msg)}</i>",
                ParagraphStyle(
                    "ImpTrunc",
                    parent=normal,
                    fontSize=8,
                    textColor=color_text,
                ),
            )
        )

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
