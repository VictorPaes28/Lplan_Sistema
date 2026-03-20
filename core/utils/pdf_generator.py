"""
Módulo de Geração de PDF para Diário de Obra V2.0 - LPLAN

Redesign com Design System: paleta institucional, hierarquia tipográfica,
header azul, cards de efetivo, seções com borda esquerda, ocorrências em destaque
laranja, galeria com legendas, assinaturas em grid, rodapé paginado.

Gerado exclusivamente com ReportLab (compatível cPanel/Servihost).
"""
import os
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any
from io import BytesIO
from django.conf import settings
from django.core.files.base import ContentFile
import logging

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None

logger = logging.getLogger(__name__)


def _safe_int(value, default=0):
    """Converte para int sem lançar; evita int(None) e tipos incompatíveis."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ReportLab (única dependência de PDF; já no requirements, funciona em cPanel)
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        Image as RLImage,
        PageBreak,
    )
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True

    # Design system (cores) — disponível apenas com ReportLab
    COLOR_PRIMARY = colors.HexColor('#1A3A5C')
    COLOR_PRIMARY_LIGHT = colors.HexColor('#2E6DA4')
    COLOR_ACCENT = colors.HexColor('#E8F0F8')
    COLOR_SUCCESS = colors.HexColor('#2E7D32')
    COLOR_WARNING = colors.HexColor('#F57C00')
    COLOR_TEXT = colors.HexColor('#1C1C1C')
    COLOR_TEXT_SECONDARY = colors.HexColor('#5A5A5A')
    COLOR_BORDER = colors.HexColor('#D0D9E3')
    COLOR_SURFACE = colors.HexColor('#F7F9FC')
    COLOR_OCCURRENCE_BG = colors.HexColor('#FFF3E0')

    class _RDOCanvas(canvas.Canvas):
        """Canvas para rodapé com numeração. Usa getPageNumber() (API pública) e tamanho da página."""
        def __init__(self, *args, generated_date_str='', **kwargs):
            self._generated_date = generated_date_str
            super().__init__(*args, **kwargs)

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
                    pn = None

                pn = _safe_int(pn, 1)  # nunca int(None)

                self.setStrokeColor(COLOR_BORDER)
                self.setFillColor(COLOR_TEXT_SECONDARY)
                self.setFont('Helvetica', 7.5)
                self.line(20 * mm, 14 * mm, w - 20 * mm, 14 * mm)
                footer = "LPlan – Gestão de Obras  |  Documento gerado em %s  |  Página %s" % (
                    self._generated_date,
                    pn,
                )
                self.drawCentredString(w / 2, 10 * mm, footer)
            except Exception as footer_err:
                logger.debug("Erro no rodapé do PDF: %s", footer_err)
            finally:
                self.restoreState()
                super().showPage()

except ImportError:
    REPORTLAB_AVAILABLE = False
    canvas = None

# Compatibilidade: views importam esses nomes (sempre False — usamos só ReportLab)
WEASYPRINT_AVAILABLE = False
XHTML2PDF_AVAILABLE = False


class ImageOptimizer:
    """
    Otimização de imagens para PDF: redimensiona (max 800px), converte para RGB/JPEG,
    remove EXIF. Usa nomes temporários únicos para evitar conflitos em geração simultânea.
    """

    MAX_WIDTH = 800
    JPEG_QUALITY = 80

    @classmethod
    def optimize_image_for_pdf(
        cls,
        image_path: str,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Otimiza uma imagem para inclusão em PDF.
        Se output_path for None, grava em arquivo temporário com nome único (thread-safe).
        Sem Pillow (PIL), retorna o path original sem otimizar.
        """
        if not PIL_AVAILABLE or not Image:
            return image_path
        try:
            with Image.open(image_path) as img:
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    rgb_img.paste(
                        img,
                        mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None,
                    )
                    img = rgb_img
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                width, height = img.size
                if width is None or height is None:
                    return image_path
                if width > cls.MAX_WIDTH:
                    ratio = cls.MAX_WIDTH / float(width)
                    new_height = _safe_int(height * ratio, cls.MAX_WIDTH)
                    if new_height <= 0:
                        new_height = 1
                    img = img.resize(
                        (cls.MAX_WIDTH, new_height),
                        Image.Resampling.LANCZOS,
                    )

                if output_path is None:
                    fd, output_path = tempfile.mkstemp(
                        suffix='.jpg',
                        prefix='lplan_pdf_',
                    )
                    os.close(fd)

                img.save(
                    output_path,
                    'JPEG',
                    quality=cls.JPEG_QUALITY,
                    optimize=True,
                    exif=b'',
                )
                logger.debug("Imagem otimizada: %s -> %s", image_path, output_path)
                return output_path
        except Exception as e:
            logger.error("Erro ao otimizar imagem %s: %s", image_path, e)
            return image_path

    @classmethod
    def get_optimized_image_path(cls, image_field) -> Optional[str]:
        """
        Retorna o caminho da imagem otimizada (pdf_optimized se existir, senão otimiza).
        Retorna None se não houver arquivo local (ex.: storage remoto S3).
        """
        if not image_field or not image_field.name:
            return None

        if hasattr(image_field.instance, 'pdf_optimized') and image_field.instance.pdf_optimized:
            optimized_path = getattr(image_field.instance.pdf_optimized, 'path', None)
            if optimized_path and os.path.exists(optimized_path):
                return optimized_path

        original_path = getattr(image_field, 'path', None)
        if not original_path or not os.path.exists(original_path):
            return None

        optimized_path = cls.optimize_image_for_pdf(original_path)
        if not optimized_path or not os.path.exists(optimized_path):
            return None

        if hasattr(image_field.instance, 'pdf_optimized'):
            try:
                with open(optimized_path, 'rb') as f:
                    image_field.instance.pdf_optimized.save(
                        os.path.basename(optimized_path),
                        ContentFile(f.read()),
                        save=False,
                    )
            except Exception as e:
                logger.debug("Não foi possível salvar pdf_optimized: %s", e)

        return optimized_path


def _get_logo_absolute_path() -> Optional[str]:
    """Retorna o caminho absoluto da logo LPLAN (static/core/images/lplan_logo.png)."""
    base = Path(settings.BASE_DIR)
    logo_dir = base / 'core' / 'static' / 'core' / 'images'
    for name in ('lplan_logo.png', 'lplan_logo.jpg', 'lplan_logo.jpeg'):
        p = logo_dir / name
        if p.exists():
            return str(p)
    return None


def get_rdo_pdf_filename(project, date_obj, suffix='') -> str:
    """
    Nome padrão do arquivo PDF do RDO: RDO_[CODIGO]_[DATA]_[NOME_DA_OBRA].pdf
    date_obj: date do diário; suffix: opcional (ex: '_detalhado', '_sem_fotos').
    """
    import re
    code = (project.code or '').strip() or 'RDO'
    data_str = date_obj.strftime('%Y%m%d')
    name = (project.name or '').strip()
    name_safe = re.sub(r'[^\w\s-]', '', name)
    name_safe = re.sub(r'[\s]+', '_', name_safe).strip('_') or 'OBRA'
    return "RDO_%s_%s_%s%s.pdf" % (code, data_str, name_safe[:80], suffix)


class PDFGenerator:
    """
    Geração de PDF de Diário de Obra exclusivamente com ReportLab (padrão RQ-10 / GesttControl).
    """

    # Cores institucionais (azul marinho / cinza escuro, sem emojis)
    COLOR_HEADER = colors.HexColor('#1e293b')
    COLOR_HEADER_TEXT = colors.white
    COLOR_ROW_ALT = colors.HexColor('#f8fafc')
    COLOR_TEXT = colors.HexColor('#334155')
    COLOR_SUBTITLE = colors.HexColor('#64748b')

    @staticmethod
    def generate_diary_pdf(
        diary_id: int,
        output_path: Optional[str] = None,
        pdf_type: str = 'normal',
    ) -> Optional[BytesIO]:
        """
        Gera o PDF do diário (ReportLab puro).
        Retorna BytesIO com o PDF ou None se output_path for informado (grava em arquivo).
        """
        if not REPORTLAB_AVAILABLE:
            logger.error("ReportLab não disponível. Instale: pip install reportlab")
            raise RuntimeError("Geração de PDF requer a biblioteca ReportLab.")

        from core.models import ConstructionDiary, DiaryLaborEntry

        try:
            diary = ConstructionDiary.objects.select_related(
                'project',
                'created_by',
                'reviewed_by',
            ).prefetch_related(
                'images',
                'videos',
                'attachments',
                'work_logs__activity',
                'work_logs__resources_labor',
                'work_logs__resources_equipment',
                'occurrences',
                'occurrences__tags',
            ).get(pk=diary_id)
        except ConstructionDiary.DoesNotExist:
            raise ConstructionDiary.DoesNotExist(
                f"Diário com ID {diary_id} não encontrado."
            )

        if pdf_type == 'no_photos':
            images = diary.images.none()
        else:
            images = diary.images.filter(is_approved_for_report=True).order_by('uploaded_at')

        images_with_paths: List[Dict[str, Any]] = []
        for image in images:
            path = None
            pdf_opt = getattr(image.pdf_optimized, 'path', None) if image.pdf_optimized else None
            orig = getattr(image.image, 'path', None) if image.image else None
            if pdf_opt and os.path.exists(pdf_opt):
                path = pdf_opt
            elif orig and os.path.exists(orig):
                try:
                    path = ImageOptimizer.get_optimized_image_path(image.image)
                except Exception as e:
                    logger.debug("Imagem %s sem path local, omitindo do PDF: %s", image.pk, e)
            if path and os.path.exists(path):
                images_with_paths.append({
                    'image': image,
                    'absolute_path': path,
                })
            else:
                images_with_paths.append({'image': image, 'absolute_path': ''})

        work_logs = list(
            diary.work_logs.select_related('activity')
            .prefetch_related('resources_labor', 'resources_equipment', 'equipment_through__equipment')
            .all()
        )

        labor_by_type = {'I': {}, 'D': {}, 'T': {}}
        equipment_count = {}
        for wl in work_logs:
            for labor in wl.resources_labor.all():
                labor_type = labor.labor_type
                key = f"{labor.name or ''}_{labor.role or ''}_{labor.company or ''}"
                if labor_type in labor_by_type:
                    if key not in labor_by_type[labor_type]:
                        labor_by_type[labor_type][key] = {'labor': labor, 'count': 0}
                    labor_by_type[labor_type][key]['count'] += 1
            for thru in wl.equipment_through.all():
                eq = thru.equipment
                qty = _safe_int(getattr(thru, 'quantity', 1), 1)
                key = f"{getattr(eq, 'code', '')}_{getattr(eq, 'name', '')}"
                if key not in equipment_count:
                    equipment_count[key] = {'equipment': eq, 'count': 0}
                equipment_count[key]['count'] += qty

        total_indirect = sum(i['count'] for i in labor_by_type['I'].values())
        total_direct = sum(i['count'] for i in labor_by_type['D'].values())
        total_third_party = sum(i['count'] for i in labor_by_type['T'].values())
        total_labor = total_indirect + total_direct + total_third_party
        total_equipment = sum(i['count'] for i in equipment_count.values())

        labor_entries_by_category = None
        try:
            entries = DiaryLaborEntry.objects.filter(diary=diary).select_related(
                'cargo', 'cargo__category'
            ).order_by('cargo__category__order', 'company', 'cargo__name')
            if entries.exists():
                labor_entries_by_category = {'indireta': [], 'direta': [], 'terceirizada': {}}
                for e in entries:
                    slug = e.cargo.category.slug
                    try:
                        qty = _safe_int(e.quantity, 0)
                    except Exception:
                        qty = 0
                    item = {'cargo_name': e.cargo.name, 'quantity': qty}
                    if slug == 'terceirizada':
                        company = e.company or '(Sem empresa)'
                        if company not in labor_entries_by_category['terceirizada']:
                            labor_entries_by_category['terceirizada'][company] = []
                        labor_entries_by_category['terceirizada'][company].append(item)
                    elif slug in labor_entries_by_category:
                        labor_entries_by_category[slug].append(item)
                labor_entries_by_category['terceirizada'] = [
                    {'company': k, 'items': v}
                    for k, v in labor_entries_by_category['terceirizada'].items()
                ]
                total_indirect = sum((x.get('quantity') or 0) for x in labor_entries_by_category['indireta'])
                total_direct = sum((x.get('quantity') or 0) for x in labor_entries_by_category['direta'])
                total_third_party = sum(
                    (x.get('quantity') or 0)
                    for block in labor_entries_by_category['terceirizada']
                    for x in block['items']
                )
                total_labor = total_indirect + total_direct + total_third_party
        except Exception:
            pass

        occurrences = list(
            diary.occurrences.select_related('created_by')
            .prefetch_related('tags')
            .order_by('created_at')
        )

        days_elapsed = None
        days_remaining = None
        if getattr(diary.project, 'start_date', None) and getattr(diary.project, 'end_date', None):
            if diary.date >= diary.project.start_date:
                days_elapsed = (diary.date - diary.project.start_date).days
            if diary.date <= diary.project.end_date:
                days_remaining = (diary.project.end_date - diary.date).days

        logo_path = _get_logo_absolute_path()

        pdf_buffer = BytesIO()
        try:
            PDFGenerator._build_diary_pdf_reportlab(
                pdf_buffer,
                diary=diary,
                work_logs=work_logs,
                labor_by_type=labor_by_type,
                labor_entries_by_category=labor_entries_by_category,
                total_indirect=total_indirect,
                total_direct=total_direct,
                total_third_party=total_third_party,
                total_labor=total_labor,
                equipment_count=equipment_count,
                total_equipment=total_equipment,
                images_with_paths=images_with_paths,
                occurrences=occurrences,
                pdf_type=pdf_type,
                logo_absolute_path=logo_path,
                days_elapsed=days_elapsed,
                days_remaining=days_remaining,
            )
        except Exception as e:
            import traceback
            logger.error(
                "Erro COMPLETO ao gerar PDF do diário %s:\n%s",
                diary_id,
                traceback.format_exc(),
            )
            raise

        if output_path:
            with open(output_path, 'wb') as f:
                f.write(pdf_buffer.getvalue())
            logger.info("PDF gerado com sucesso: %s", output_path)
            return None

        pdf_buffer.seek(0)
        logger.info("PDF do diário %s gerado com sucesso (ReportLab).", diary_id)
        return pdf_buffer

    @staticmethod
    def _build_diary_pdf_reportlab(
        buffer_io: BytesIO,
        diary,
        work_logs,
        labor_by_type: Dict,
        labor_entries_by_category: Optional[Dict],
        total_indirect: int,
        total_direct: int,
        total_third_party: int,
        total_labor: int,
        equipment_count: Dict,
        total_equipment: int,
        images_with_paths: List[Dict],
        occurrences: List,
        pdf_type: str,
        logo_absolute_path: Optional[str] = None,
        days_elapsed: Optional[int] = None,
        days_remaining: Optional[int] = None,
    ) -> None:
        """Monta o documento PDF com ReportLab (redesign RDO: design system, header azul, cards, seções com borda)."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm, mm
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            Image as RLImage,
        )
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_CENTER

        # Margens A4: 20mm lateral, 18mm topo/rodapé (espaço para rodapé fixo)
        doc = SimpleDocTemplate(
            buffer_io,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
        )
        styles = getSampleStyleSheet()
        # Hierarquia tipográfica (Inter → Helvetica como fallback)
        title_style = ParagraphStyle(
            name='RDOTitle',
            parent=styles['Normal'],
            fontSize=18,
            alignment=TA_LEFT,
            spaceAfter=2,
            textColor=COLOR_PRIMARY,
            fontName='Helvetica-Bold',
        )
        heading_style = ParagraphStyle(
            name='Section',
            parent=styles['Normal'],
            fontSize=10,
            spaceBefore=8,
            spaceAfter=4,
            alignment=TA_LEFT,
            textColor=COLOR_PRIMARY,
            fontName='Helvetica-Bold',
        )
        normal_style = ParagraphStyle(
            name='NormalRDO',
            parent=styles['Normal'],
            fontSize=9,
            alignment=TA_LEFT,
            textColor=COLOR_TEXT,
            spaceAfter=2,
            leading=11,
        )
        label_style = ParagraphStyle(
            name='Label',
            parent=normal_style,
            fontSize=8.5,
            textColor=COLOR_TEXT_SECONDARY,
            fontName='Helvetica',
        )
        table_header_style = ParagraphStyle(
            name='TableHeader',
            parent=normal_style,
            textColor=colors.white,
            fontName='Helvetica-Bold',
            fontSize=8,
        )
        story = []

        # —— HEADER AZUL INSTITUCIONAL ——
        proj = diary.project
        try:
            weekday = diary.date.strftime('%A')
            wd_pt = {'Monday': 'Segunda-feira', 'Tuesday': 'Terça-feira', 'Wednesday': 'Quarta-feira', 'Thursday': 'Quinta-feira', 'Friday': 'Sexta-feira', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}.get(weekday, weekday)
        except Exception:
            wd_pt = ''
        report_num = getattr(diary, 'report_number', None)
        start_d = getattr(proj, 'start_date', None)
        end_d = getattr(proj, 'end_date', None)
        contratante = getattr(proj, 'client_name', None) and proj.client_name.strip()
        resp_tec = getattr(proj, 'responsible', None) and proj.responsible.strip()
        endereco = getattr(proj, 'address', None) and proj.address.strip()

        header_title = Paragraph(
            "<font color='white' size='14'><b>RELATÓRIO DIÁRIO DE OBRA</b></font>",
            ParagraphStyle(name='H1', fontName='Helvetica-Bold', fontSize=14, textColor=colors.white),
        )
        header_sub = Paragraph(
            "<font color='white' size='9'>RDO n° %s · Código %s · %s · %s</font>" % (
                report_num if report_num is not None else '—',
                proj.code or '—',
                diary.date.strftime('%d/%m/%Y'),
                wd_pt,
            ),
            ParagraphStyle(name='H2', fontName='Helvetica', fontSize=9, textColor=colors.white),
        )
        if logo_absolute_path and os.path.exists(logo_absolute_path):
            try:
                logo_img = RLImage(logo_absolute_path, width=1.8 * cm, height=0.8 * cm)
                header_rows = [[logo_img, header_title], [header_sub, Paragraph(' ', ParagraphStyle(name='E', fontSize=1))]]
                col_widths = [2 * cm, 15 * cm]
            except Exception:
                header_rows = [[header_title], [header_sub]]
                col_widths = [17 * cm]
        else:
            header_rows = [[header_title], [header_sub]]
            col_widths = [17 * cm]
        tbl_header = Table(header_rows, colWidths=col_widths)
        tbl_header.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_PRIMARY),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(tbl_header)

        # Linha separadora e bloco de dados da obra (fundo azul)
        obra_line = Paragraph(
            "<font color='white' size='9'><b>OBRA:</b> %s</font>" % ((proj.name or '—')[:50],),
            ParagraphStyle(name='ObraH', fontName='Helvetica', fontSize=9, textColor=colors.white),
        )
        line2 = Paragraph(
            "<font color='white' size='8'>Contratante: %s &nbsp;&nbsp; Resp. Técnico: %s</font>" % (
                (contratante or '—')[:40],
                (resp_tec or '—')[:35],
            ),
            ParagraphStyle(name='Line2', fontName='Helvetica', fontSize=8, textColor=colors.white),
        )
        line3 = Paragraph(
            "<font color='white' size='8'>Local: %s</font>" % ((endereco or '—')[:90]),
            ParagraphStyle(name='Line3', fontName='Helvetica', fontSize=8, textColor=colors.white),
        )
        line4 = Paragraph(
            "<font color='white' size='8'>Início: %s &nbsp;&nbsp; Término: %s &nbsp;&nbsp; Dias corridos: %s</font>" % (
                start_d.strftime('%d/%m/%y') if start_d else '—',
                end_d.strftime('%d/%m/%y') if end_d else '—',
                str(days_elapsed) if days_elapsed is not None else '—',
            ),
            ParagraphStyle(name='Line4', fontName='Helvetica', fontSize=8, textColor=colors.white),
        )
        sep_row = Table([[Paragraph(' ', ParagraphStyle(name='Sep', fontSize=1))]], colWidths=[17 * cm])
        sep_row.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (0, 0), 0.5, colors.HexColor('#FFFFFF')),
            ('BACKGROUND', (0, 0), (0, 0), COLOR_PRIMARY),
            ('TOPPADDING', (0, 0), (0, 0), 4),
            ('BOTTOMPADDING', (0, 0), (0, 0), 4),
        ]))
        header_block2 = Table([
            [obra_line],
            [line2],
            [line3],
            [line4],
        ], colWidths=[17 * cm])
        header_block2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_PRIMARY),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(sep_row)
        story.append(header_block2)
        story.append(Spacer(1, 0.35 * cm))

        # Atividades / Serviços — seção com borda esquerda; conteúdo em tabela aninhada (1 flowable por célula)
        act_title = Paragraph(
            "<font color='#1A3A5C'><b>ATIVIDADES / SERVIÇOS</b></font>",
            ParagraphStyle(name='SecTitle', fontName='Helvetica-Bold', fontSize=10, textColor=COLOR_PRIMARY),
        )
        act_rows = [[act_title], [Spacer(1, 0.08 * cm)]]
        if work_logs:
            for wl in work_logs:
                text = "• %s – %s" % (
                    getattr(wl.activity, 'code', '') or '',
                    getattr(wl.activity, 'name', '') or '',
                )
                if getattr(wl, 'notes', None) and wl.notes.strip():
                    text += " <i>(%s)</i>" % (wl.notes[:100].replace('\n', ' ') if wl.notes else '')
                act_rows.append([Paragraph(text, normal_style)])
        else:
            act_rows.append([Paragraph("Nenhuma atividade registrada.", normal_style)])
        content_width = 17 * cm - 3 * mm
        # Largura interna menor que a célula para evitar availWidth negativo no ReportLab (padding da célula)
        inner_width = content_width - 0.6 * cm
        inner_act = Table(act_rows, colWidths=[inner_width])
        inner_act.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), COLOR_ACCENT),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        sect_act = Table([[Paragraph(' ', ParagraphStyle(name='Bar', fontSize=1)), inner_act]], colWidths=[3 * mm, content_width])
        sect_act.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), COLOR_PRIMARY),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ('LEFTPADDING', (0, 0), (0, -1), 0),
            ('RIGHTPADDING', (0, 0), (0, -1), 0),
        ]))
        story.append(sect_act)
        story.append(Spacer(1, 0.2 * cm))

        # Gestão de Efetivo: UMA tabela com 3 colunas (Indireto | Direto | Terceiros) como no RQ-10
        has_efetivo = (
            (labor_entries_by_category and (
                labor_entries_by_category.get('indireta')
                or labor_entries_by_category.get('direta')
                or labor_entries_by_category.get('terceirizada')
            ))
            or (labor_by_type and (labor_by_type.get('I') or labor_by_type.get('D') or labor_by_type.get('T')))
        )
        if has_efetivo:
            # Monta listas de células por coluna (cada célula = um Paragraph)
            def _lab_name(lab):
                n = getattr(lab, 'name', None)
                if n:
                    return str(n)
                if hasattr(lab, 'get_role_display') and callable(getattr(lab, 'get_role_display')):
                    return str(lab.get_role_display() or '—')
                return '—'
            col_i = [Paragraph('EFETIVO INDIRETO (LPLAN)', table_header_style)]
            indireta_rows = labor_entries_by_category.get('indireta', []) if labor_entries_by_category else []
            if not indireta_rows and labor_by_type.get('I'):
                for item in labor_by_type['I'].values():
                    col_i.append(Paragraph(_lab_name(item['labor']) + ' ' + str(item['count']), normal_style))
            else:
                for item in indireta_rows:
                    col_i.append(Paragraph((item.get('cargo_name') or '—') + ' ' + str(item['quantity']), normal_style))
            col_i.append(Paragraph('TOTAL ' + str(total_indirect), normal_style))

            col_d = [Paragraph('EFETIVO DIRETO', table_header_style)]
            direta_rows = labor_entries_by_category.get('direta', []) if labor_entries_by_category else []
            if not direta_rows and labor_by_type.get('D'):
                for item in labor_by_type['D'].values():
                    col_d.append(Paragraph(_lab_name(item['labor']) + ' ' + str(item['count']), normal_style))
            else:
                for item in direta_rows:
                    col_d.append(Paragraph((item.get('cargo_name') or '—') + ' ' + str(item['quantity']), normal_style))
            col_d.append(Paragraph('TOTAL ' + str(total_direct), normal_style))

            col_t = [Paragraph('EFETIVO TERCEIROS', table_header_style)]
            terceiros_rows = []
            if labor_entries_by_category and labor_entries_by_category.get('terceirizada'):
                for block in labor_entries_by_category['terceirizada']:
                    for item in block['items']:
                        col_t.append(Paragraph((block.get('company') or '—') + ' ' + (item.get('cargo_name') or '') + ' ' + str(item['quantity']), normal_style))
            elif labor_by_type.get('T'):
                for item in labor_by_type['T'].values():
                    lab = item['labor']
                    col_t.append(Paragraph((getattr(lab, 'company', None) or '—') + ' ' + _lab_name(lab) + ' ' + str(item['count']), normal_style))
            col_t.append(Paragraph('TOTAL ' + str(total_third_party), normal_style))

            n = max(len(col_i), len(col_d), len(col_t))
            empty = Paragraph(' ', normal_style)
            for i in range(len(col_i), n):
                col_i.append(empty)
            for i in range(len(col_d), n):
                col_d.append(empty)
            for i in range(len(col_t), n):
                col_t.append(empty)
            efetivo_data = [[col_i[r], col_d[r], col_t[r]] for r in range(n)]
            t_efetivo = Table(efetivo_data, colWidths=[5.5 * cm, 5.5 * cm, 5.5 * cm])
            t_efetivo.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), COLOR_PRIMARY),
                ('BACKGROUND', (1, 0), (1, 0), COLOR_PRIMARY),
                ('BACKGROUND', (2, 0), (2, 0), COLOR_PRIMARY),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                ('INNERGRID', (0, 0), (-1, -1), 0.25, COLOR_BORDER),
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, COLOR_ACCENT]),
                ('BACKGROUND', (0, n - 1), (0, n - 1), COLOR_ACCENT),
                ('BACKGROUND', (1, n - 1), (1, n - 1), COLOR_ACCENT),
                ('BACKGROUND', (2, n - 1), (2, n - 1), COLOR_ACCENT),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(t_efetivo)
            story.append(Spacer(1, 0.12 * cm))
            total_row = Table([[Paragraph(
                "EFETIVO TOTAL GERAL: %s" % total_labor,
                ParagraphStyle(name='EfetivoTotal', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=TA_CENTER),
            )]], colWidths=[17 * cm])
            total_row.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), COLOR_PRIMARY),
                ('ALIGN', (0, 0), (-1, -1), 'CENTRE'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(total_row)
            story.append(Spacer(1, 0.25 * cm))

        # Equipamentos
        if equipment_count:
            story.append(Paragraph("EQUIPAMENTOS", heading_style))
            data = [[Paragraph('Equipamento', table_header_style), Paragraph('Qtd', table_header_style)]]
            for item in equipment_count.values():
                eq = item['equipment']
                data.append([
                    Paragraph('%s – %s' % (getattr(eq, 'code', '') or '', getattr(eq, 'name', '') or ''), normal_style),
                    Paragraph(str(item['count']), normal_style),
                ])
            data.append([Paragraph('TOTAL', normal_style), Paragraph(str(total_equipment), normal_style)])
            t_eq = Table(data, colWidths=[10 * cm, 2 * cm])
            t_eq.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_ACCENT]),
            ]))
            story.append(t_eq)
            story.append(Spacer(1, 0.25 * cm))

        # Ocorrência de Chuvas (como no RQ-10)
        story.append(Paragraph("OCORRÊNCIA DE CHUVAS", heading_style))
        rain = getattr(diary, 'rain_occurrence', None)
        rain_label = {'F': 'Fraca', 'M': 'Média', 'S': 'Forte'}.get(rain, 'Nenhuma')
        text = "Intensidade da Chuva: %s" % rain_label
        if getattr(diary, 'pluviometric_index', None) is not None:
            text += " | Índice Pluviométrico: %s mm" % diary.pluviometric_index
        story.append(Paragraph(text, normal_style))
        if getattr(diary, 'rain_observations', None) and diary.rain_observations.strip():
            story.append(Paragraph(
                "OBSERVAÇÕES: %s" % diary.rain_observations[:300].replace('\n', '<br/>'),
                normal_style,
            ))
        story.append(Spacer(1, 0.2 * cm))

        # Condições climáticas detalhadas (quando preenchidas)
        weather_parts = []
        if getattr(diary, 'weather_conditions', None) and diary.weather_conditions.strip():
            weather_parts.append(Paragraph("<b>Condições climáticas:</b> %s" % diary.weather_conditions[:400].replace('\n', '<br/>'), normal_style))
        w_morn_c = getattr(diary, 'weather_morning_condition', None)
        w_morn_w = getattr(diary, 'weather_morning_workable', None)
        if w_morn_c or w_morn_w:
            cond = {'B': 'Bom', 'R': 'Ruim'}.get(w_morn_c, '—')
            trab = {'T': 'Trabalhável', 'N': 'Não Trabalhável'}.get(w_morn_w, '—')
            weather_parts.append(Paragraph("Clima Manhã: %s / %s" % (cond, trab), normal_style))
        w_aft_c = getattr(diary, 'weather_afternoon_condition', None)
        w_aft_w = getattr(diary, 'weather_afternoon_workable', None)
        if w_aft_c or w_aft_w:
            cond = {'B': 'Bom', 'R': 'Ruim'}.get(w_aft_c, '—')
            trab = {'T': 'Trabalhável', 'N': 'Não Trabalhável'}.get(w_aft_w, '—')
            weather_parts.append(Paragraph("Clima Tarde: %s / %s" % (cond, trab), normal_style))
        if getattr(diary, 'weather_night_enabled', False) and (getattr(diary, 'weather_night_type', None) or getattr(diary, 'weather_night_workable', None)):
            t = {'C': 'Claro', 'N': 'Nublado', 'CH': 'Chuvoso'}.get(getattr(diary, 'weather_night_type', None), '—')
            p = {'P': 'Praticável', 'I': 'Impraticável'}.get(getattr(diary, 'weather_night_workable', None), '—')
            weather_parts.append(Paragraph("Clima Noite: %s / %s" % (t, p), normal_style))
        if weather_parts:
            story.append(Paragraph("CONDIÇÕES CLIMÁTICAS DETALHADAS", heading_style))
            for p in weather_parts:
                story.append(p)
            story.append(Spacer(1, 0.15 * cm))

        # Horas trabalhadas
        if getattr(diary, 'work_hours', None) is not None:
            story.append(Paragraph("<b>Horas trabalhadas:</b> %s h" % diary.work_hours, normal_style))
            story.append(Spacer(1, 0.1 * cm))

        # Acidentes, Paralisações, Riscos, Incidentes, Fiscalizações, DDS, Observações gerais (só se preenchidos)
        def _sec(title, value, max_len=1200):
            if not value or not str(value).strip():
                return
            story.append(Paragraph("<b>%s</b>" % title, normal_style))
            story.append(Paragraph(str(value).replace('\n', '<br/>')[:max_len], normal_style))
            story.append(Spacer(1, 0.12 * cm))
        _sec("Acidentes:", getattr(diary, 'accidents', None))
        _sec("Paralisações:", getattr(diary, 'stoppages', None))
        _sec("Riscos Eminentes:", getattr(diary, 'imminent_risks', None))
        _sec("Outros Incidentes:", getattr(diary, 'incidents', None))
        _sec("Fiscalizações:", getattr(diary, 'inspections', None))
        _sec("DDS (Discurso Diário de Segurança):", getattr(diary, 'dds', None))
        _sec("Observações Gerais:", getattr(diary, 'general_notes', None))

        # Ocorrências e Observações — tabela aninhada (1 flowable por célula); destaque laranja se houver ocorrências
        if occurrences or (getattr(diary, 'deliberations', None) and diary.deliberations.strip()):
            occ_title = Paragraph(
                "<font color='#1A3A5C'><b>OCORRÊNCIAS E OBSERVAÇÕES</b></font>" + (
                    " &nbsp; <font color='#F57C00' size='8'><b>⚠ OCORRÊNCIA</b></font>" if occurrences else ""
                ),
                ParagraphStyle(name='OccTitle', fontName='Helvetica-Bold', fontSize=10, textColor=COLOR_PRIMARY),
            )
            occ_rows = [[occ_title], [Spacer(1, 0.08 * cm)]]
            if occurrences:
                for occ in occurrences:
                    desc = getattr(occ, 'description', '') or ''
                    desc = desc.replace('\n', '<br/>')[:800]
                    tags = list(occ.tags.values_list('name', flat=True)[:5])
                    tag_str = (' | '.join(tags)) if tags else ''
                    if tag_str:
                        occ_rows.append([Paragraph("<b>%s</b> %s" % (tag_str, desc), normal_style)])
                    else:
                        occ_rows.append([Paragraph(desc or '—', normal_style)])
            if getattr(diary, 'deliberations', None) and diary.deliberations.strip():
                occ_rows.append([Paragraph("<b>DELIBERAÇÕES:</b>", normal_style)])
                occ_rows.append([Paragraph(
                    diary.deliberations.replace('\n', '<br/>')[:1500],
                    normal_style,
                )])
            border_color = COLOR_WARNING if occurrences else COLOR_PRIMARY
            bg_color = COLOR_OCCURRENCE_BG if occurrences else COLOR_ACCENT
            inner_width = content_width - 0.6 * cm
            inner_occ = Table(occ_rows, colWidths=[inner_width])
            inner_occ.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), bg_color),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]))
            sect_occ = Table([[Paragraph(' ', ParagraphStyle(name='Bar2', fontSize=1)), inner_occ]], colWidths=[3 * mm, content_width])
            sect_occ.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), border_color),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (0, -1), 0),
                ('RIGHTPADDING', (0, 0), (0, -1), 0),
                ('LEFTPADDING', (1, 0), (1, 0), 10),
                ('RIGHTPADDING', (1, 0), (1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ]))
            story.append(sect_occ)
            story.append(Spacer(1, 0.25 * cm))

        # Registro Fotográfico — tabela aninhada; incluir imagem só se o arquivo for válido (PIL)
        if pdf_type != 'no_photos':
            photo_title = Paragraph(
                "<font color='#1A3A5C'><b>REGISTRO FOTOGRÁFICO</b></font>",
                ParagraphStyle(name='PhotoTitle', fontName='Helvetica-Bold', fontSize=10, textColor=COLOR_PRIMARY),
            )
            content_width = 17 * cm - 3 * mm
            img_w, img_h = 6.5 * cm, 4.9 * cm
            photo_rows = [[photo_title], [Spacer(1, 0.12 * cm)]]
            valid = [i for i in images_with_paths if i.get('absolute_path') and os.path.exists(i['absolute_path'])]
            if valid:
                photo_cells = []
                for row_start in range(0, len(valid), 2):
                    row_images = valid[row_start: row_start + 2]
                    row_cells = []
                    for item in row_images:
                        path = item['absolute_path']
                        cap = (item.get('image') and getattr(item['image'], 'caption', None)) or 'Foto'
                        uploaded_at = item.get('image') and getattr(item['image'], 'uploaded_at', None)
                        if uploaded_at:
                            try:
                                dt_str = uploaded_at.strftime('%d/%m/%Y %H:%M')
                                cap = "%s – %s" % (dt_str, (cap or 'Foto')[:35])
                            except Exception:
                                cap = str(cap)[:50]
                        else:
                            cap = str(cap)[:50]
                        cap_para = Paragraph(
                            "<i>%s</i>" % cap,
                            ParagraphStyle(name='Cap', parent=normal_style, fontSize=8, textColor=COLOR_TEXT_SECONDARY),
                        )
                        img_flowable = None
                        if PIL_AVAILABLE and Image:
                            try:
                                with Image.open(path) as pil_img:
                                    pil_img.verify()
                                img_flowable = RLImage(path, width=img_w, height=img_h)
                            except Exception as e:
                                logger.debug("Imagem inválida ou inacessível para PDF: %s", e)
                        if img_flowable is None:
                            try:
                                img_flowable = RLImage(path, width=img_w, height=img_h)
                            except Exception as e:
                                logger.debug("RLImage falhou para %s: %s", path, e)
                                img_flowable = Paragraph("Imagem indisponível", label_style)
                        cell_content = Table([[img_flowable], [cap_para]], colWidths=[img_w + 0.3 * cm])
                        cell_content.setStyle(TableStyle([
                            ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                            ('BACKGROUND', (0, 0), (-1, -1), COLOR_SURFACE),
                            ('TOPPADDING', (0, 0), (-1, -1), 4),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ]))
                        row_cells.append(cell_content)
                    if len(row_cells) == 1:
                        row_cells.append(Paragraph(' ', ParagraphStyle(name='E2', fontSize=1)))
                    if row_cells:
                        photo_cells.append(row_cells)
                if photo_cells:
                    t_photo = Table(photo_cells, colWidths=[img_w + 0.5 * cm] * 2)
                    t_photo.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ]))
                    photo_rows.append([t_photo])
                else:
                    photo_rows.append([Paragraph("Nenhum registro fotográfico.", label_style)])
            else:
                photo_rows.append([Paragraph("Nenhum registro fotográfico.", label_style)])
            inner_width = content_width - 0.6 * cm
            inner_photo = Table(photo_rows, colWidths=[inner_width])
            inner_photo.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), COLOR_SURFACE),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ]))
            sect_photo = Table([[Paragraph(' ', ParagraphStyle(name='BarP', fontSize=1)), inner_photo]], colWidths=[3 * mm, content_width])
            sect_photo.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), COLOR_PRIMARY),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                ('LEFTPADDING', (0, 0), (0, -1), 0),
                ('RIGHTPADDING', (0, 0), (0, -1), 0),
            ]))
            story.append(sect_photo)
            story.append(Spacer(1, 0.2 * cm))

        # Assinatura — bloco único de responsável pelo preenchimento
        story.append(Spacer(1, 0.4 * cm))
        insp = getattr(diary, 'inspection_responsible', None) and diary.inspection_responsible.strip()
        sig_style = ParagraphStyle(name='Sig', parent=normal_style, fontSize=9.5, fontName='Helvetica-Bold', textColor=COLOR_TEXT)
        sig_cargo_style = ParagraphStyle(name='SigCargo', parent=normal_style, fontSize=8.5, textColor=COLOR_TEXT_SECONDARY)

        def _sig_block(name, cargo):
            line_t = Table([['']], colWidths=[4 * cm])
            line_t.setStyle(TableStyle([('LINEBELOW', (0, 0), (0, 0), 1, COLOR_TEXT_SECONDARY)]))
            return Table([
                [line_t],
                [Paragraph(name or '_________________________', sig_style)],
                [Paragraph(cargo or '', sig_cargo_style)],
            ], colWidths=[5.5 * cm])

        c1 = _sig_block(insp, "Responsável pelo preenchimento")
        sig_table = Table([[c1]], colWidths=[17 * cm])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(sig_table)

        # Rodapé com numeração: canvasmaker via functools.partial para preservar assinatura esperada pelo ReportLab
        import functools
        from datetime import date
        generated_date_str = date.today().strftime('%d/%m/%Y')
        canvas_class = functools.partial(_RDOCanvas, generated_date_str=generated_date_str)
        doc.build(story, canvasmaker=canvas_class)
