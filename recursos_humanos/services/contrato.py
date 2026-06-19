"""Contrato de admissão — geração de PDF e arquivamento do documento assinado (ZapSign externo)."""

from __future__ import annotations

import logging
import os
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from recursos_humanos.models import Colaborador, ContratoAdmissao

logger = logging.getLogger(__name__)

_MESES_PT = (
    'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
)


def _data_extenso_pt(d):
    return f'{d.day} de {_MESES_PT[d.month - 1]} de {d.year}'


def obter_ou_criar_contrato(colaborador: Colaborador) -> ContratoAdmissao:
    contrato, _ = ContratoAdmissao.objects.get_or_create(
        colaborador=colaborador,
        defaults={'status': ContratoAdmissao.Status.PENDENTE},
    )
    return contrato


def _contrato_pdf_palette():
    """Paleta institucional alinhada ao RDO (core.utils.pdf_generator)."""
    try:
        from core.utils.pdf_generator import (
            COLOR_ACCENT,
            COLOR_BORDER,
            COLOR_PRIMARY,
            COLOR_PRIMARY_LIGHT,
            COLOR_SURFACE,
            COLOR_TEXT,
            COLOR_TEXT_SECONDARY,
            _get_logo_absolute_path,
            _safe_pdf_text,
        )
        return {
            'primary': COLOR_PRIMARY,
            'primary_light': COLOR_PRIMARY_LIGHT,
            'accent': COLOR_ACCENT,
            'surface': COLOR_SURFACE,
            'text': COLOR_TEXT,
            'text_secondary': COLOR_TEXT_SECONDARY,
            'border': COLOR_BORDER,
            'header_bg': COLOR_ACCENT,
            'logo_path': _get_logo_absolute_path(),
            'safe_text': _safe_pdf_text,
        }
    except Exception:
        from reportlab.lib import colors

        return {
            'primary': colors.HexColor('#1A3A5C'),
            'primary_light': colors.HexColor('#2E6DA4'),
            'accent': colors.HexColor('#E8F0F8'),
            'surface': colors.HexColor('#F7F9FC'),
            'text': colors.HexColor('#1C1C1C'),
            'text_secondary': colors.HexColor('#5A5A5A'),
            'border': colors.HexColor('#D0D9E3'),
            'header_bg': colors.HexColor('#EAF2FB'),
            'logo_path': None,
            'safe_text': lambda v, default='': str(v or default),
        }


def _make_contrato_canvas(generated_date_str: str):
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    class ContratoCanvas(canvas.Canvas):
        def showPage(self):
            self.saveState()
            try:
                palette = _contrato_pdf_palette()
                ps = getattr(self, '_pagesize', None)
                if ps and len(ps) >= 2 and ps[0] is not None and ps[1] is not None:
                    w, h = float(ps[0]), float(ps[1])
                else:
                    w, h = 595.28, 841.89

                try:
                    pn = self.getPageNumber()
                except Exception:
                    pn = 1

                self.setStrokeColor(palette['border'])
                self.setFillColor(palette['text_secondary'])
                self.setFont('Helvetica', 7.5)
                self.line(20 * mm, 14 * mm, w - 20 * mm, 14 * mm)
                footer = (
                    f'LPlan – Recursos Humanos  |  Documento gerado em {generated_date_str}  |  '
                    f'Página {pn}'
                )
                self.drawCentredString(w / 2, 10 * mm, footer)
            except Exception as exc:
                logger.debug('Rodapé do PDF de contrato: %s', exc)
            finally:
                self.restoreState()
                super().showPage()

    return ContratoCanvas


def gerar_pdf_contrato(colaborador: Colaborador) -> bytes:
    """Gera PDF do contrato com identidade visual LPlan (padrão RDO)."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    palette = _contrato_pdf_palette()
    safe = palette['safe_text']

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=12 * mm,
        bottomMargin=18 * mm,
    )
    content_width = doc.width
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'ContratoTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=17,
        alignment=TA_CENTER,
        textColor=palette['primary'],
        spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        'ContratoSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        textColor=palette['primary_light'],
        spaceAfter=0,
    )
    section_style = ParagraphStyle(
        'ContratoSection',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        textColor=palette['primary'],
        spaceBefore=4,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        'ContratoBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=15,
        alignment=TA_JUSTIFY,
        textColor=palette['text'],
        spaceAfter=6,
    )
    label_style = ParagraphStyle(
        'ContratoLabel',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=palette['text_secondary'],
    )
    value_style = ParagraphStyle(
        'ContratoValue',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=palette['text'],
    )
    muted_style = ParagraphStyle(
        'ContratoMuted',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=palette['text_secondary'],
        alignment=TA_CENTER,
    )
    clause_title_style = ParagraphStyle(
        'ContratoClause',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=palette['primary'],
        spaceBefore=10,
        spaceAfter=4,
    )

    def section_block(title: str):
        inner = Paragraph(safe(title), section_style)
        tbl = Table([[inner]], colWidths=[content_width])
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), palette['surface']),
            ('LINEBEFORE', (0, 0), (0, -1), 3, palette['primary']),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        return tbl

    def kv_table(rows, section_titles: set[int] | None = None):
        section_titles = section_titles or set()
        data = []
        for idx, (label, value) in enumerate(rows):
            if idx in section_titles:
                data.append([
                    Paragraph(f'<b>{safe(label)}</b>', value_style),
                    Paragraph('', body_style),
                ])
            else:
                data.append([
                    Paragraph(safe(label), label_style),
                    Paragraph(safe(value, '—'), body_style),
                ])
        tbl = Table(data, colWidths=[4.8 * cm, content_width - 4.8 * cm])
        style_cmds = [
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.25, palette['border']),
        ]
        for idx in section_titles:
            style_cmds.append(('BACKGROUND', (0, idx), (-1, idx), palette['accent']))
            style_cmds.append(('SPAN', (0, idx), (-1, idx)))
        even = 0
        for idx in range(len(rows)):
            if idx in section_titles:
                continue
            if even % 2 == 1:
                style_cmds.append(('BACKGROUND', (0, idx), (-1, idx), palette['surface']))
            even += 1
        tbl.setStyle(TableStyle(style_cmds))
        return tbl

    obras_str = ', '.join(colaborador.obras.values_list('nome', flat=True)) or '—'
    data_inicio = (
        colaborador.data_admissao.strftime('%d/%m/%Y')
        if colaborador.data_admissao
        else '—'
    )
    gerado_em = timezone.localdate()
    gestor = (colaborador.gestor_aprovador or '').strip() or '—'
    origem = (colaborador.deslocamento_origem or '').strip()
    destino = (colaborador.deslocamento_destino or '').strip()

    story = []

    header_title = Paragraph('<b>CONTRATO DE TRABALHO</b>', title_style)
    header_sub = Paragraph(
        f'Admissão · {safe(colaborador.tipo_contrato or "CLT")} · Ref. #{colaborador.pk}',
        subtitle_style,
    )
    header_date = Paragraph(
        f'Gerado em {gerado_em.strftime("%d/%m/%Y")} · Para assinatura eletrônica (ZapSign)',
        subtitle_style,
    )

    logo_path = palette['logo_path']
    if logo_path and os.path.exists(logo_path):
        try:
            max_logo_w = 4.6 * cm
            max_logo_h = 1.1 * cm
            logo_img = RLImage(logo_path, width=max_logo_w, height=max_logo_h)
            logo_col_w = 5 * cm
            text_col_w = max(content_width - (2 * logo_col_w), 1.0 * cm)
            text_block = Table(
                [[header_title], [Spacer(1, 2)], [header_sub], [header_date]],
                colWidths=[text_col_w],
                hAlign='CENTER',
            )
            text_block.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            header_rows = [[logo_img, text_block, Paragraph(' ', muted_style)]]
            col_widths = [logo_col_w, text_col_w, logo_col_w]
        except Exception as exc:
            logger.debug('Logo no PDF de contrato: %s', exc)
            header_rows = [[header_title], [header_sub], [header_date]]
            col_widths = [content_width]
    else:
        header_rows = [[header_title], [header_sub], [header_date]]
        col_widths = [content_width]

    tbl_header = Table(header_rows, colWidths=col_widths, hAlign='CENTER')
    tbl_header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), palette['header_bg']),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(tbl_header)

    sep = Table([[Paragraph(' ', ParagraphStyle(name='Sep', fontSize=1))]], colWidths=[content_width])
    sep.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (0, 0), 1.2, palette['primary']),
        ('TOPPADDING', (0, 0), (0, 0), 0),
        ('BOTTOMPADDING', (0, 0), (0, 0), 0),
    ]))
    story.append(sep)

    summary_rows = [
        [
            Paragraph('Colaborador', label_style),
            Paragraph(safe(colaborador.nome), value_style),
            Paragraph('CPF', label_style),
            Paragraph(safe(colaborador.cpf), value_style),
        ],
        [
            Paragraph('Cargo', label_style),
            Paragraph(safe(colaborador.cargo), value_style),
            Paragraph('Início previsto', label_style),
            Paragraph(safe(data_inicio), value_style),
        ],
    ]
    if origem or destino:
        summary_rows.append([
            Paragraph('Origem', label_style),
            Paragraph(safe(origem, '—'), value_style),
            Paragraph('Destino', label_style),
            Paragraph(safe(destino, '—'), value_style),
        ])
    summary = Table(
        summary_rows,
        colWidths=[2.6 * cm, (content_width - 5.2 * cm) / 2, 2.6 * cm, (content_width - 5.2 * cm) / 2],
    )
    summary.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.5, palette['border']),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, palette['border']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    story.append(summary)
    story.append(Spacer(1, 0.35 * cm))

    story.append(section_block('DADOS DO CONTRATADO E DO VÍNCULO'))
    story.append(Spacer(1, 0.15 * cm))
    dados_rows = [
        ('CONTRATADO', ''),
        ('Nome completo', colaborador.nome),
        ('CPF', colaborador.cpf),
        ('RG', colaborador.rg or '—'),
        ('Endereço', colaborador.endereco or '—'),
        ('VÍNCULO EMPREGATÍCIO', ''),
        ('Cargo / função', colaborador.cargo),
        ('Tipo de contrato', colaborador.tipo_contrato or 'CLT'),
        ('Salário', colaborador.salario or 'A definir'),
        ('Data de início', data_inicio),
        ('Obra(s) / alocação', obras_str),
        ('Gestor aprovador', gestor),
    ]
    if origem:
        dados_rows.append(('Cidade de origem', origem))
    if destino:
        dados_rows.append(('Cidade de destino', destino))
    from recursos_humanos.services.reembolsos import reembolsos_colaborador, total_reembolsos

    reembolsos = reembolsos_colaborador(colaborador)
    reembolso_section_idx = None
    if reembolsos:
        reembolso_section_idx = len(dados_rows)
        dados_rows.append(('REEMBOLSOS PREVISTOS', ''))
        for idx, item in enumerate(reembolsos, start=1):
            linha = item.get('titulo') or f'Item {idx}'
            if item.get('descricao'):
                linha += f' — {item["descricao"]}'
            if item.get('valor'):
                linha += f' — R$ {item["valor"]}'
            dados_rows.append((f'Reembolso {idx}', linha))
        total_reemb = total_reembolsos(reembolsos)
        if total_reemb:
            dados_rows.append(('Total de reembolsos', f'R$ {total_reemb}'))
    section_titles = {0, 5}
    if reembolso_section_idx is not None:
        section_titles.add(reembolso_section_idx)
    story.append(kv_table(dados_rows, section_titles=section_titles))
    story.append(Spacer(1, 0.35 * cm))

    story.append(section_block('CLÁUSULAS CONTRATUAIS'))
    story.append(Spacer(1, 0.15 * cm))
    story.append(Paragraph(
        'Pelo presente instrumento particular, as partes abaixo qualificadas '
        'ajustam as condições de trabalho, nos termos da legislação vigente.',
        body_style,
    ))

    clausulas = [
        (
            '1. DO OBJETO',
            f'O(A) CONTRATADO(A), {colaborador.nome}, portador(a) do CPF '
            f'{colaborador.cpf}, é admitido(a) para exercer a função de '
            f'{colaborador.cargo}, com alocação na(s) obra(s): {obras_str}.',
        ),
        (
            '2. DA REMUNERAÇÃO',
            f'O(A) CONTRATADO(A) perceberá remuneração mensal de '
            f'{colaborador.salario or "valor a definir em folha"}, '
            f'paga até o 5º dia útil do mês subsequente ao da prestação dos serviços.',
        ),
        (
            '3. DA JORNADA',
            'A jornada de trabalho será de 44 (quarenta e quatro) horas semanais, '
            'de segunda a sábado, com intervalos e descansos conforme a legislação '
            'trabalhista aplicável.',
        ),
        (
            '4. DAS OBRIGAÇÕES',
            'O(A) CONTRATADO(A) compromete-se a cumprir as normas internas da '
            'empresa, utilizar EPIs quando exigidos, zelar pelos equipamentos e '
            'manter sigilo sobre informações confidenciais.',
        ),
        (
            '5. DA LEGISLAÇÃO APLICÁVEL',
            'Este contrato rege-se pela Consolidação das Leis do Trabalho (CLT) '
            'e demais normas trabalhistas, previdenciárias e de segurança do '
            'trabalho aplicáveis à atividade.',
        ),
    ]

    for titulo, texto in clausulas:
        story.append(Paragraph(safe(titulo), clause_title_style))
        story.append(Paragraph(safe(texto), body_style))

    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        f'E, por estarem de pleno acordo, firmam o presente em duas vias de igual teor. '
        f'Recife, {_data_extenso_pt(gerado_em)}.',
        body_style,
    ))
    story.append(Spacer(1, 0.5 * cm))

    story.append(section_block('ASSINATURAS'))
    story.append(Spacer(1, 0.25 * cm))

    sig_col_w = (content_width - 0.4 * cm) / 2
    sig_table = Table(
        [
            [
                Paragraph('<b>LPLAN ENGENHARIA</b><br/>EMPREGADOR', value_style),
                Paragraph(f'<b>{safe(colaborador.nome)}</b><br/>CONTRATADO(A)', value_style),
            ],
            [Spacer(1, 2.2 * cm), Spacer(1, 2.2 * cm)],
            [
                Paragraph('_________________________________________<br/>Assinatura e carimbo', muted_style),
                Paragraph('_________________________________________<br/>Assinatura do colaborador', muted_style),
            ],
        ],
        colWidths=[sig_col_w, sig_col_w],
        hAlign='CENTER',
    )
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOX', (0, 0), (0, -1), 0.5, palette['border']),
        ('BOX', (1, 0), (1, -1), 0.5, palette['border']),
        ('BACKGROUND', (0, 0), (-1, 0), palette['surface']),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph(
        'Documento gerado automaticamente pelo sistema LPlan. '
        'Utilize este arquivo no ZapSign para coleta das assinaturas.',
        muted_style,
    ))

    doc.build(story, canvasmaker=_make_contrato_canvas(gerado_em.strftime('%d/%m/%Y')))
    buffer.seek(0)
    return buffer.read()


def salvar_rascunho_contrato(contrato: ContratoAdmissao, colaborador: Colaborador) -> bytes:
    """Gera PDF, salva rascunho no contrato e retorna os bytes para download."""
    pdf_bytes = gerar_pdf_contrato(colaborador)
    cpf_limpo = (colaborador.cpf or '').replace('.', '').replace('-', '')
    nome_arquivo = f'contrato_rascunho_{cpf_limpo}_{colaborador.pk}.pdf'
    contrato.pdf_contrato.save(nome_arquivo, ContentFile(pdf_bytes), save=True)
    if contrato.status != ContratoAdmissao.Status.CONCLUIDO:
        contrato.status = ContratoAdmissao.Status.PENDENTE
        contrato.save(update_fields=['status'])
    return pdf_bytes


def salvar_contrato_assinado(contrato: ContratoAdmissao, arquivo, user) -> bool:
    """
    Salva o PDF assinado (vindo do ZapSign) e marca contrato como concluído.
    Ativa o colaborador na etapa 5.
    """
    from recursos_humanos.services.admissao_actions import _autor, registrar_historico

    if not arquivo:
        return False

    contrato.pdf_contrato.save(
        f'contrato_assinado_{contrato.colaborador.pk}.pdf',
        ContentFile(arquivo.read()),
        save=False,
    )
    contrato.status = ContratoAdmissao.Status.CONCLUIDO
    contrato.concluido_em = timezone.now()
    contrato.save()

    colaborador = contrato.colaborador
    registrar_historico(
        colaborador,
        4,
        'Contrato assinado arquivado pelo RH.',
        _autor(user),
    )

    try:
        telefone_rh = getattr(settings, 'RH_WHATSAPP_NOTIFICACAO', None)
        if telefone_rh:
            from whatsapp_ia.views_webhook import _enviar_mensagem_whatsapp

            _enviar_mensagem_whatsapp(
                telefone_rh,
                f'✅ *Contrato assinado — RH/DP*\n'
                f'👤 {colaborador.nome}\n'
                f'PDF assinado arquivado no sistema.',
            )
    except Exception:
        pass

    return True
