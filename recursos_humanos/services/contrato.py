"""Contrato de admissão — geração de PDF e arquivamento do documento assinado (ZapSign externo)."""

from __future__ import annotations

import logging
import os
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone

from recursos_humanos.models import Colaborador, ContratoAdmissao, PrazoContrato

logger = logging.getLogger(__name__)

_MESES_PT = (
    'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
)

_EMPREGADOR_NOME = 'LPLAN ENGENHARIA LTDA.'
_EMPREGADOR_ENDERECO = 'Recife — Pernambuco'


def _data_extenso_pt(d):
    return f'{d.day} de {_MESES_PT[d.month - 1]} de {d.year}'


def obter_ou_criar_contrato(colaborador: Colaborador) -> ContratoAdmissao:
    contrato, _ = ContratoAdmissao.objects.get_or_create(
        colaborador=colaborador,
        defaults={'status': ContratoAdmissao.Status.PENDENTE},
    )
    return contrato


def _logo_path():
    try:
        from core.utils.pdf_generator import _get_logo_absolute_path
        path = _get_logo_absolute_path()
        if path and os.path.exists(path):
            return path
    except Exception:
        pass
    return None


def _safe_text(value, default='—'):
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _make_contrato_canvas(generated_date_str: str):
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    class ContratoCanvas(canvas.Canvas):
        def showPage(self):
            self.saveState()
            try:
                ps = getattr(self, '_pagesize', None)
                if ps and len(ps) >= 2 and ps[0] is not None and ps[1] is not None:
                    w, h = float(ps[0]), float(ps[1])
                else:
                    w, h = 595.28, 841.89
                try:
                    pn = self.getPageNumber()
                except Exception:
                    pn = 1
                self.setFont('Times-Roman', 8)
                self.setFillColorRGB(0.35, 0.35, 0.35)
                self.line(25 * mm, 15 * mm, w - 25 * mm, 15 * mm)
                self.drawCentredString(
                    w / 2,
                    10 * mm,
                    f'{_EMPREGADOR_NOME}  ·  Documento gerado em {generated_date_str}  ·  Pág. {pn}',
                )
            except Exception as exc:
                logger.debug('Rodapé do PDF de contrato: %s', exc)
            finally:
                self.restoreState()
                super().showPage()

    return ContratoCanvas


def _tem_periodo_experiencia(colaborador: Colaborador) -> bool:
    from recursos_humanos.services.prazo_contrato import colaborador_recebe_prazo_teste_clt

    return colaborador_recebe_prazo_teste_clt(colaborador)


def gerar_pdf_contrato(colaborador: Colaborador) -> bytes:
    """Gera PDF do contrato em formato jurídico formal."""
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import Image as RLImage, Paragraph, SimpleDocTemplate, Spacer

    from recursos_humanos.services.prazo_contrato import obter_data_admissao_oficial

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=20 * mm,
        bottomMargin=22 * mm,
    )
    content_width = doc.width
    gerado_em = timezone.localdate()

    title_style = ParagraphStyle(
        'Title',
        fontName='Times-Bold',
        fontSize=13,
        leading=16,
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        'Subtitle',
        fontName='Times-Roman',
        fontSize=10,
        leading=13,
        alignment=TA_CENTER,
        spaceAfter=14,
    )
    body_style = ParagraphStyle(
        'Body',
        fontName='Times-Roman',
        fontSize=11,
        leading=16,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
    )
    clause_title_style = ParagraphStyle(
        'ClauseTitle',
        fontName='Times-Bold',
        fontSize=11,
        leading=14,
        spaceBefore=12,
        spaceAfter=4,
    )
    center_style = ParagraphStyle(
        'Center',
        fontName='Times-Roman',
        fontSize=11,
        leading=14,
        alignment=TA_CENTER,
        spaceBefore=8,
        spaceAfter=8,
    )

    obras_str = ', '.join(colaborador.obras.values_list('nome', flat=True)) or 'conforme escala da empresa'
    data_admissao = obter_data_admissao_oficial(colaborador) or colaborador.data_admissao
    data_inicio = data_admissao.strftime('%d/%m/%Y') if data_admissao else 'a definir'
    empregador = _safe_text(colaborador.empresa, _EMPREGADOR_NOME)
    salario = _safe_text(colaborador.salario, 'conforme registrado em folha de pagamento')
    tipo_contrato = _safe_text(colaborador.tipo_contrato, 'CLT')
    gestor = _safe_text(colaborador.gestor_aprovador, 'representante da empresa')
    origem = (colaborador.deslocamento_origem or '').strip()
    destino = (colaborador.deslocamento_destino or '').strip()

    story = []

    logo = _logo_path()
    if logo:
        try:
            story.append(RLImage(logo, width=3.2 * cm, height=0.85 * cm, hAlign='CENTER'))
            story.append(Spacer(1, 0.35 * cm))
        except Exception as exc:
            logger.debug('Logo no PDF de contrato: %s', exc)

    story.append(Paragraph('CONTRATO INDIVIDUAL DE TRABALHO', title_style))
    story.append(Paragraph(
        f'({tipo_contrato})',
        subtitle_style,
    ))

    qualificacao_empregador = (
        f'<b>{_safe_text(empregador)}</b>, pessoa jurídica de direito privado, '
        f'com sede em {_EMPREGADOR_ENDERECO}, doravante denominada simplesmente '
        f'<b>EMPREGADORA</b>'
    )
    qualificacao_empregado = (
        f'<b>{_safe_text(colaborador.nome)}</b>, '
        f'portador(a) do CPF nº {_safe_text(colaborador.cpf)}, '
        f'RG nº {_safe_text(colaborador.rg)}, '
        f'residiente em {_safe_text(colaborador.endereco)}, '
        f'doravante denominado(a) <b>EMPREGADO(A)</b>'
    )

    story.append(Paragraph(
        f'Pelo presente instrumento particular, {qualificacao_empregador}, '
        f'e {qualificacao_empregado}, '
        f'têm, entre si, justo e contratado o presente Contrato Individual de Trabalho, '
        f'que se regerá pelas cláusulas e condições seguintes, bem como pelas disposições '
        f'da Consolidação das Leis do Trabalho e demais normas aplicáveis.',
        body_style,
    ))

    clausulas = [
        (
            'CLÁUSULA PRIMEIRA — DO OBJETO',
            f'A EMPREGADORA admite o(a) EMPREGADO(A) para prestar serviços na função de '
            f'<b>{_safe_text(colaborador.cargo)}</b>, com início previsto em '
            f'<b>{data_inicio}</b>, observadas as normas internas da empresa e as '
            f'instruções do gestor responsável ({gestor}).',
        ),
        (
            'CLÁUSULA SEGUNDA — DA REMUNERAÇÃO',
            f'Pela prestação dos serviços, o(a) EMPREGADO(A) perceberá remuneração mensal '
            f'de <b>{salario}</b>, paga até o 5º (quinto) dia útil do mês subsequente '
            f'ao da prestação dos serviços, mediante crédito em conta bancária indicada '
            f'pelo(a) EMPREGADO(A), quando aplicável.',
        ),
        (
            'CLÁUSULA TERCEIRA — DA JORNADA DE TRABALHO',
            'A jornada de trabalho será de 44 (quarenta e quatro) horas semanais, '
            'distribuídas de segunda a sábado, com intervalos intrajornada e interjornada '
            'em conformidade com a legislação vigente. Eventuais horas extras serão '
            'remuneradas ou compensadas nos termos da lei e das normas coletivas aplicáveis.',
        ),
        (
            'CLÁUSULA QUARTA — DO LOCAL DE PRESTAÇÃO DOS SERVIÇOS',
            f'O(A) EMPREGADO(A) prestará serviços preferencialmente na(s) obra(s) ou '
            f'unidade(s): <b>{obras_str}</b>.'
            + (
                f' Deslocamento previsto: de <b>{origem}</b> para <b>{destino}</b>.'
                if origem and destino else ''
            ),
        ),
        (
            'CLÁUSULA QUINTA — DAS OBRIGAÇÕES DO EMPREGADO',
            'O(A) EMPREGADO(A) compromete-se a desempenhar suas atividades com zelo, '
            'pontualidade e diligência; cumprir normas de segurança e uso de EPIs; '
            'observar o regulamento interno da EMPREGADORA; e manter sigilo sobre '
            'informações confidenciais a que tiver acesso.',
        ),
    ]

    if _tem_periodo_experiencia(colaborador):
        clausulas.append((
            'CLÁUSULA SEXTA — DO PERÍODO DE EXPERIÊNCIA',
            'Fica estabelecido período de experiência de até 90 (noventa) dias, '
            'podendo ser dividido em dois períodos de 45 (quarenta e cinco) dias cada, '
            'durante o qual poderá ser verificada a conveniência da continuidade do '
            'vínculo empregatício por ambas as partes, nos termos do art. 445 da CLT.',
        ))
        clausula_legislacao = (
            'CLÁUSULA SÉTIMA — DA LEGISLAÇÃO APLICÁVEL',
            'O presente contrato rege-se pela CLT e demais normas trabalhistas, '
            'previdenciárias e de segurança do trabalho aplicáveis, bem como por eventuais '
            'normas coletivas da categoria.',
        )
    else:
        clausula_legislacao = (
            'CLÁUSULA SEXTA — DA LEGISLAÇÃO APLICÁVEL',
            'O presente contrato rege-se pela CLT e demais normas trabalhistas, '
            'previdenciárias e de segurança do trabalho aplicáveis, bem como por eventuais '
            'normas coletivas da categoria.',
        )
    clausulas.append(clausula_legislacao)

    from recursos_humanos.services.reembolsos import reembolsos_colaborador, total_reembolsos

    reembolsos = reembolsos_colaborador(colaborador)
    if reembolsos:
        linhas_reemb = []
        for idx, item in enumerate(reembolsos, start=1):
            linha = item.get('titulo') or f'Item {idx}'
            if item.get('descricao'):
                linha += f' — {item["descricao"]}'
            if item.get('valor'):
                linha += f' — R$ {item["valor"]}'
            linhas_reemb.append(linha)
        total_reemb = total_reembolsos(reembolsos)
        texto_reemb = (
            'Ficam previstos os seguintes reembolsos, conforme comprovação e política interna: '
            + '; '.join(linhas_reemb)
            + (f'. Total estimado: R$ {total_reemb}.' if total_reemb else '.')
        )
        numeral = 'OITAVA' if _tem_periodo_experiencia(colaborador) else 'SÉTIMA'
        clausulas.append((
            f'CLÁUSULA {numeral} — DOS REEMBOLSOS',
            texto_reemb,
        ))

    for titulo, texto in clausulas:
        story.append(Paragraph(titulo, clause_title_style))
        story.append(Paragraph(texto, body_style))

    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        f'E, por estarem assim justos e contratados, firmam o presente instrumento em '
        f'2 (duas) vias de igual teor e forma, na presença das testemunhas abaixo, '
        f'para que produza os seus jurídicos efeitos.',
        body_style,
    ))
    story.append(Paragraph(
        f'{_EMPREGADOR_ENDERECO.split("—")[0].strip()}, {_data_extenso_pt(gerado_em)}.',
        center_style,
    ))
    story.append(Spacer(1, 1.0 * cm))

    from reportlab.platypus import Table, TableStyle

    sig_w = (content_width - 1.2 * cm) / 2
    sig_label = ParagraphStyle(
        'SigLabel',
        fontName='Times-Roman',
        fontSize=10,
        leading=13,
        alignment=TA_CENTER,
    )
    sig_name = ParagraphStyle(
        'SigName',
        fontName='Times-Bold',
        fontSize=10,
        leading=13,
        alignment=TA_CENTER,
        spaceBefore=4,
    )
    sig_table = Table(
        [
            [
                Paragraph('_________________________________________', sig_label),
                Paragraph('_________________________________________', sig_label),
            ],
            [
                Paragraph(_safe_text(empregador), sig_name),
                Paragraph(_safe_text(colaborador.nome), sig_name),
            ],
            [
                Paragraph('EMPREGADORA', sig_label),
                Paragraph('EMPREGADO(A)', sig_label),
            ],
        ],
        colWidths=[sig_w, sig_w],
        hAlign='CENTER',
    )
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, 0), 24),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(sig_table)

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


def obter_contrato_admissao_arquivado(colaborador: Colaborador) -> ContratoAdmissao | None:
    """Contrato assinado arquivado na etapa ZapSign (PDF disponível)."""
    try:
        contrato = colaborador.contrato_admissao
    except ContratoAdmissao.DoesNotExist:
        return None
    if (
        contrato.status == ContratoAdmissao.Status.CONCLUIDO
        and contrato.pdf_contrato
    ):
        return contrato
    return None


def documento_contrato_assinado_json(colaborador: Colaborador) -> dict | None:
    """Representação do PDF assinado para a aba Documentos do perfil."""
    contrato = obter_contrato_admissao_arquivado(colaborador)
    if not contrato:
        return None

    data_emissao = None
    if contrato.data_admissao_oficial:
        data_emissao = contrato.data_admissao_oficial.strftime('%d/%m/%Y')

    detalhe = None
    if contrato.concluido_em:
        detalhe = (
            f'Arquivado em {timezone.localtime(contrato.concluido_em).strftime("%d/%m/%Y")}'
        )

    return {
        'id': f'contrato-{contrato.pk}',
        'nome': 'Contrato de trabalho assinado (ZapSign)',
        'categoria': 'contratos',
        'status': 'received',
        'data_emissao': data_emissao,
        'detalhe': detalhe,
        'vencimento': None,
        'dias_restantes': None,
        'alerta_vencimento': False,
        'vencido': False,
        'reenvio_solicitado': False,
        'pode_solicitar_reenvio': False,
        'url_solicitar_reenvio': None,
        'pode_aprovar': False,
        'url_aprovar': None,
        'url_redirect': None,
        'obrigatorio': True,
        'tem_arquivo': True,
        'tem_validade': False,
        'url_arquivo': reverse(
            'recursos_humanos:contrato_download',
            args=[colaborador.pk],
        ),
        'es_contrato_admissao': True,
    }
