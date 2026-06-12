"""Contrato de admissão — geração de PDF e arquivamento do documento assinado (ZapSign externo)."""

from __future__ import annotations

from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from recursos_humanos.models import Colaborador, ContratoAdmissao

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


def gerar_pdf_contrato(colaborador: Colaborador) -> bytes:
    """Gera PDF do contrato com dados do colaborador (ReportLab)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=14,
        spaceAfter=6,
        alignment=1,
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=10,
        leading=16,
        spaceAfter=8,
    )

    story = []
    story.append(Paragraph('LPLAN ENGENHARIA', title_style))
    story.append(Paragraph('CONTRATO DE TRABALHO', title_style))
    story.append(Spacer(1, 0.5 * cm))

    obras_str = ', '.join(colaborador.obras.values_list('nome', flat=True)) or '—'
    data_inicio = (
        colaborador.data_admissao.strftime('%d/%m/%Y')
        if colaborador.data_admissao
        else '—'
    )

    dados = [
        ['CONTRATADO', ''],
        ['Nome completo', colaborador.nome],
        ['CPF', colaborador.cpf],
        ['RG', colaborador.rg or '—'],
        ['Endereço', colaborador.endereco or '—'],
        ['', ''],
        ['VÍNCULO EMPREGATÍCIO', ''],
        ['Cargo', colaborador.cargo],
        ['Tipo de contrato', colaborador.tipo_contrato or 'CLT'],
        ['Salário', colaborador.salario or '—'],
        ['Data de início', data_inicio],
        ['Obra(s)', obras_str],
    ]

    table = Table(dados, colWidths=[5 * cm, 11 * cm])
    table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#374151')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
        ('BACKGROUND', (0, 6), (-1, 6), colors.HexColor('#f3f4f6')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 6), (-1, 6), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('ROWBACKGROUNDS', (0, 1), (-1, 5), [colors.white, colors.HexColor('#fafafa')]),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.5 * cm))

    clausulas = [
        (
            '1. OBJETO',
            f'O CONTRATADO, {colaborador.nome}, portador do CPF '
            f'{colaborador.cpf}, é admitido para exercer a função '
            f'de {colaborador.cargo} na(s) obra(s): {obras_str}.',
        ),
        (
            '2. REMUNERAÇÃO',
            f'O CONTRATADO receberá salário mensal de '
            f'{colaborador.salario or "a definir"}, pago até o '
            f'5º dia útil do mês subsequente.',
        ),
        (
            '3. JORNADA',
            'A jornada de trabalho será de 44 horas semanais, '
            'de segunda a sábado, conforme legislação vigente.',
        ),
        (
            '4. LEGISLAÇÃO APLICÁVEL',
            'O presente contrato rege-se pela Consolidação das '
            'Leis do Trabalho (CLT) e demais normas trabalhistas '
            'aplicáveis.',
        ),
    ]

    for titulo, texto in clausulas:
        story.append(Paragraph(titulo, ParagraphStyle(
            'ClausulaTitle',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            spaceAfter=4,
            spaceBefore=8,
        )))
        story.append(Paragraph(texto, body_style))

    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(
        f'Recife, {_data_extenso_pt(timezone.localdate())}.',
        body_style,
    ))

    doc.build(story)
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
    if colaborador.etapa_admissao == 4:
        colaborador.etapa_admissao = 5
        colaborador.status = Colaborador.Status.ATIVO
        colaborador.save(update_fields=['etapa_admissao', 'status', 'atualizado_em'])
        registrar_historico(
            colaborador,
            5,
            'Contrato assinado enviado pelo RH. Colaborador ativado.',
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
                f'PDF assinado arquivado no sistema. Colaborador ativado.',
            )
    except Exception:
        pass

    return True
