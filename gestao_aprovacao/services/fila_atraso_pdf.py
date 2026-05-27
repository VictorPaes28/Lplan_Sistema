"""PDF da fila de pedidos parados há bastante tempo (card da home GestControll)."""
from __future__ import annotations

import io
import os
from collections import Counter
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape as xml_escape


def _pdf_esc(text) -> str:
    return xml_escape(str(text or ""))


def _logo_path():
    logo_dir = os.path.join(settings.BASE_DIR, "core", "static", "core", "images")
    for name in (
        "lpla-logo-pdf-transparent.png",
        "lpla-logo-pdf.png",
        "lplan-logo2.png",
        "lplan_logo.png",
    ):
        p = os.path.join(logo_dir, name)
        if os.path.exists(p):
            return p
    return None


def _clip(v, n=80) -> str:
    txt = str(v or "").strip()
    if len(txt) <= n:
        return txt or "—"
    return txt[: max(0, n - 3)] + "..."


def _fmt_date(dt) -> str:
    if not dt:
        return "—"
    try:
        return timezone.localtime(dt).strftime("%d/%m/%Y")
    except Exception:
        return "—"


def _obra_paragraph(item: dict, style) -> Paragraph:
    cod = (item.get("obra_codigo") or "").strip()
    nom = (item.get("obra_nome") or "").strip()
    emp = (item.get("empresa_nome") or "").strip()
    if cod and nom:
        linha1 = f"{cod} — {nom}"
    else:
        linha1 = cod or nom or "—"
    if emp:
        html = f"{_pdf_esc(_clip(linha1, 55))}<br/><font size='7' color='#64748b'>{_pdf_esc(_clip(emp, 40))}</font>"
    else:
        html = _pdf_esc(_clip(linha1, 60))
    return Paragraph(html, style)


def _tipo_credor_paragraph(item: dict, style) -> Paragraph:
    tipo = _clip(item.get("tipo_solicitacao_display"), 28)
    credor = _clip(item.get("nome_credor"), 38)
    return Paragraph(
        f"{_pdf_esc(tipo)}<br/><font size='7' color='#475569'>{_pdf_esc(credor)}</font>",
        style,
    )


def _build_pdf_header(
    *,
    width: float,
    dias_limite: int,
    usuario_nome: str,
    escopo_admin: bool,
    total_pedidos: int,
    color_primary,
    color_accent,
    color_border,
    styles,
) -> Table:
    """Cabeçalho do relatório com logo, título e metadados em faixa destacada."""
    from reportlab.platypus import Image as RLImage

    escopo_txt = "Alcance administrativo" if escopo_admin else "Alcance do aprovador"
    gerado_em = timezone.now().strftime("%d/%m/%Y às %H:%M")

    title_style = ParagraphStyle(
        "FilaHdrTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=color_primary,
        leading=17,
        spaceAfter=2,
    )
    tagline_style = ParagraphStyle(
        "FilaHdrTag",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        textColor=colors.HexColor("#475569"),
        leading=11,
    )
    meta_style = ParagraphStyle(
        "FilaHdrMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=colors.HexColor("#334155"),
        leading=11,
    )

    title_block = Paragraph(
        "<font color='#1A3A5C'><b>Pedidos há bastante tempo na fila</b></font>",
        title_style,
    )
    tagline = Paragraph(
        "<font color='#64748b'>GestControll · Relatório de acompanhamento da fila de aprovação</font>",
        tagline_style,
    )
    meta_row = Paragraph(
        f"<b>Gerado:</b> {_pdf_esc(gerado_em)} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Por:</b> {_pdf_esc(usuario_nome)} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>{_pdf_esc(escopo_txt)}</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>{total_pedidos}</b> pedido(s) listado(s)",
        meta_style,
    )
    criterio = Paragraph(
        f"<font color='#9a3412'><b>Critério:</b></font> "
        f"<font color='#1e293b'>status <b>Pendente</b> ou <b>Reaprovação</b>, "
        f"parados há <b>mais de {dias_limite} dias</b> "
        f"(contagem desde o envio; sem envio, desde a criação)</font>",
        meta_style,
    )

    logo_col = 4.2 * cm
    text_col = max(width - logo_col - 0.4 * cm, 8 * cm)
    text_rows = [[title_block], [tagline], [Spacer(1, 0.12 * cm)], [meta_row], [criterio]]
    text_inner = Table(text_rows, colWidths=[text_col])
    text_inner.setStyle(
        TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )

    lp = _logo_path()
    if lp:
        logo = RLImage(lp, width=3.2 * cm, height=0.78 * cm)
        logo_wrap = Table([[logo]], colWidths=[3.5 * cm])
        logo_wrap.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.5, color_border),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        logo_cell_content = logo_wrap
    else:
        logo_cell_content = Paragraph(
            "<font color='#1A3A5C'><b>LPLAN</b></font>",
            title_style,
        )

    hdr = Table(
        [[logo_cell_content, text_inner]],
        colWidths=[logo_col, width - logo_col],
    )
    hdr.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), color_accent),
            ("BOX", (0, 0), (-1, -1), 0.6, color_border),
            ("LINEBELOW", (0, 0), (-1, -1), 2, color_primary),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (0, 0), 12),
            ("RIGHTPADDING", (-1, 0), (-1, -1), 14),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("LEFTPADDING", (1, 0), (1, 0), 10),
        ])
    )
    return hdr


def _build_resumo(pedidos: list[dict[str, Any]]) -> dict[str, Any]:
    if not pedidos:
        return {
            "total": 0,
            "pendentes": 0,
            "reaprovacao": 0,
            "media_dias": 0,
            "max_dias": 0,
            "pedido_mais_antigo": "—",
            "obras_top": [],
        }
    dias_list = [p.get("dias_na_fila", 0) for p in pedidos]
    mais_antigo = max(pedidos, key=lambda p: p.get("dias_na_fila", 0))
    status_ct = Counter(p.get("status") for p in pedidos)
    obra_ct = Counter(
        f"{p.get('obra_codigo') or ''} — {p.get('obra_nome') or 'Sem obra'}".strip(" —")
        for p in pedidos
    )
    return {
        "total": len(pedidos),
        "pendentes": status_ct.get("pendente", 0),
        "reaprovacao": status_ct.get("reaprovacao", 0),
        "media_dias": round(sum(dias_list) / len(dias_list), 1),
        "max_dias": max(dias_list),
        "pedido_mais_antigo": f"{mais_antigo.get('codigo', '—')} ({mais_antigo.get('dias_na_fila', 0)} dias)",
        "obras_top": obra_ct.most_common(5),
    }


def build_fila_atraso_pdf(
    *,
    pedidos: list[dict[str, Any]],
    dias_limite: int,
    usuario_nome: str,
    escopo_admin: bool,
    site_url: str = "",
) -> bytes:
    color_primary = colors.HexColor("#1A3A5C")
    color_text = colors.HexColor("#1C1C1C")
    color_border = colors.HexColor("#D0D9E3")
    color_accent = colors.HexColor("#E8F0F8")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2.0 * cm,
        leftMargin=2.0 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    w = doc.width
    resumo = _build_resumo(pedidos)

    cell = ParagraphStyle(
        "FilaCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=color_text,
        leading=10,
    )
    th = ParagraphStyle(
        "FilaTH",
        parent=cell,
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=colors.white,
        alignment=TA_CENTER,
        leading=10,
    )
    section = ParagraphStyle(
        "FilaSection",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        textColor=color_primary,
        spaceBefore=8,
        spaceAfter=5,
    )
    kpi_style = ParagraphStyle(
        "FilaKPI",
        parent=cell,
        fontSize=8,
        alignment=TA_CENTER,
        leading=11,
    )

    story = []
    story.append(
        _build_pdf_header(
            width=w,
            dias_limite=dias_limite,
            usuario_nome=usuario_nome,
            escopo_admin=escopo_admin,
            total_pedidos=len(pedidos),
            color_primary=color_primary,
            color_accent=color_accent,
            color_border=color_border,
            styles=styles,
        )
    )
    story.append(Spacer(1, 0.45 * cm))

    # Resumo em uma linha — colunas iguais
    story.append(Paragraph("Resumo", section))
    kpi_cols = w / 5.0
    kpi_tbl = Table(
        [[
            Paragraph(f"<b>{resumo['total']}</b><br/>na fila", kpi_style),
            Paragraph(f"<b>{resumo['pendentes']}</b><br/>pendentes", kpi_style),
            Paragraph(f"<b>{resumo['reaprovacao']}</b><br/>reaprovação", kpi_style),
            Paragraph(f"<b>{resumo['media_dias']}</b><br/>média dias", kpi_style),
            Paragraph(f"<b>{resumo['max_dias']}</b><br/>máx. dias", kpi_style),
        ]],
        colWidths=[kpi_cols] * 5,
    )
    kpi_tbl.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), color_accent),
            ("BOX", (0, 0), (-1, -1), 0.4, color_border),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, color_border),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(kpi_tbl)
    if resumo["pedido_mais_antigo"] != "—":
        story.append(Spacer(1, 0.15 * cm))
        story.append(Paragraph(f"<font size='8'>Mais antigo: <b>{_pdf_esc(resumo['pedido_mais_antigo'])}</b></font>", cell))

    if resumo["obras_top"]:
        story.append(Spacer(1, 0.2 * cm))
        obras_txt = " · ".join(f"{_pdf_esc(_clip(nome, 35))} ({qtd})" for nome, qtd in resumo["obras_top"])
        story.append(Paragraph(f"<font size='8' color='#475569'><b>Por obra:</b> {obras_txt}</font>", cell))

    story.append(Paragraph("Lista de pedidos", section))

    if not pedidos:
        story.append(
            Paragraph(
                f"Nenhum pedido parado há mais de {dias_limite} dias no seu alcance.",
                cell,
            )
        )
    else:
        # Proporções fixas da largura útil (sempre somam 100%)
        col_widths = [
            w * 0.05,  # #
            w * 0.11,  # Pedido
            w * 0.28,  # Obra (+ empresa)
            w * 0.18,  # Tipo + credor
            w * 0.13,  # Status
            w * 0.06,  # Dias
            w * 0.10,  # Na fila desde
            w * 0.09,  # Solicitante
        ]

        headers = [
            Paragraph("#", th),
            Paragraph("Pedido", th),
            Paragraph("Obra", th),
            Paragraph("Tipo / Credor", th),
            Paragraph("Status", th),
            Paragraph("Dias", th),
            Paragraph("Na fila desde", th),
            Paragraph("Solicitante", th),
        ]
        rows = [headers]
        for idx, item in enumerate(pedidos, start=1):
            dias = item.get("dias_na_fila", 0)
            dias_html = f"<b>{dias}</b>" if dias >= dias_limite * 2 else str(dias)
            rows.append([
                Paragraph(str(idx), cell),
                Paragraph(_pdf_esc(_clip(item.get("codigo"), 16)), cell),
                _obra_paragraph(item, cell),
                _tipo_credor_paragraph(item, cell),
                Paragraph(_pdf_esc(_clip(item.get("status_display"), 22)), cell),
                Paragraph(dias_html, cell),
                Paragraph(_pdf_esc(_fmt_date(item.get("wait_from"))), cell),
                Paragraph(_pdf_esc(_clip(item.get("solicitante"), 26)), cell),
            ])

        tbl = LongTable(rows, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), color_primary),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("ALIGN", (0, 1), (0, -1), "CENTER"),
                ("ALIGN", (5, 1), (5, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, color_border),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, color_accent]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ])
        )
        story.append(tbl)

    story.append(Spacer(1, 0.2 * cm))
    story.append(
        Paragraph(
            f"<font size='7' color='#64748b'>GestControll · {len(pedidos)} pedido(s) · Uso interno LPLAN</font>",
            cell,
        )
    )

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
