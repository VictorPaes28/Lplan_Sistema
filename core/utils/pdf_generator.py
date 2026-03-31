"""
Módulo de Geração de PDF para Diário de Obra V2.0 - LPLAN

Redesign com Design System: paleta institucional, hierarquia tipográfica,
header azul, cards de efetivo, seções com borda esquerda, ocorrências em destaque
laranja, galeria com legendas, assinaturas em grid, rodapé paginado.

Gerado exclusivamente com ReportLab (compatível cPanel/Servihost).

Manutenção (sem alterar regras de negócio aqui):
- ReportLab é dependência de importação: a classe PDFGenerator referencia cores do
  ReportLab no corpo da classe; o módulo não deve ser carregado sem reportlab instalado.
- Efetivo no PDF: se ``DiaryLaborEntry`` puder ser agregado com sucesso, os totais e
  colunas usam essa fonte; caso contrário mantém-se o agregado por work logs
  (``labor_by_type``). Falhas nesse bloco são registradas em debug e o PDF segue.
- Limiares de bytes: até ~3 MiB em ``_decode_data_url_or_base64_image`` (anexos gerais);
  assinatura no PDF limita a ~2 MiB após decode (ver trecho da inspeção).
"""
import os
import tempfile
import base64
import binascii
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from io import BytesIO
from xml.sax.saxutils import escape as xml_escape
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


def _safe_pdf_text(value: Any, default: str = '') -> str:
    """
    Normaliza e escapa texto dinâmico para uso em Paragraph do ReportLab.
    Evita erros de parse com caracteres especiais como &, < e >.
    """
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return xml_escape(text, {"'": "&#39;", '"': "&quot;"})


def _safe_pdf_multiline_text(value: Any, default: str = '', max_len: Optional[int] = None) -> str:
    """
    Escapa texto dinâmico e preserva quebras de linha para Paragraph (<br/>).
    """
    if value is None:
        return default
    raw = str(value).strip()
    if not raw:
        return default
    if max_len is not None:
        raw = raw[:max_len]
    # Evita blocos com quebras excessivas que podem estourar célula de tabela.
    lines = raw.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    if len(lines) > 80:
        lines = lines[:80]
    raw = '\n'.join(lines)
    escaped = xml_escape(raw, {"'": "&#39;", '"': "&quot;"})
    return escaped.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '<br/>')


def _decode_js_escaped_text(value: Any) -> str:
    """
    Decodifica sequências JS literais (ex.: \\u0027) para melhorar legibilidade no PDF.
    """
    text = str(value or '').strip()
    if not text:
        return ''
    text = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), text)
    return text.replace("\\'", "'")


def _decode_data_url_or_base64_image(raw: str) -> Optional[bytes]:
    """
    Decodifica assinatura/anexo em data URL ou base64 puro.
    Tolera espaços/quebras (comum em payloads colados ou gerados pelo canvas) e
    evita falha com validate=True do b64decode em dados válidos mas não estritos.
    """
    if not raw or not str(raw).strip():
        return None
    s = str(raw).strip()
    if 'base64,' in s:
        s = s.split('base64,', 1)[1]
    s = ''.join(s.split())
    if not s:
        return None
    pad = (-len(s)) % 4
    if pad:
        s += '=' * pad
    try:
        decoded = base64.b64decode(s, validate=False)
    except (binascii.Error, ValueError):
        try:
            decoded = base64.urlsafe_b64decode(s)
        except (binascii.Error, ValueError):
            return None
    if not decoded:
        return None
    if len(decoded) > (3 * 1024 * 1024):
        return None
    return decoded


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
        LongTable,
        TableStyle,
        Image as RLImage,
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
    # Linha divisória (ex.: acima dos totais por coluna no bloco de efetivo) — um pouco mais escura que grey padrão
    COLOR_DIVIDER_STRONG = colors.HexColor('#64748b')
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
    """Retorna o caminho absoluto da logo LPLAN (static/core/images; prioriza lpla-logo-pdf)."""
    base = Path(settings.BASE_DIR)
    logo_dir = base / 'core' / 'static' / 'core' / 'images'
    for name in (
        'lpla-logo-pdf-transparent.png',
        'lpla-logo-pdf.png',
        'lplan-logo2.png',
        'lplan_logo.png',
        'lplan_logo.jpg',
        'lplan_logo.jpeg',
    ):
        p = logo_dir / name
        if p.exists():
            return str(p)
    return None


def get_rdo_pdf_filename(project, date_obj, suffix='') -> str:
    """
    Nome padrão do arquivo PDF do RDO: RDO_[CODIGO]_[DATA]_[NOME_DA_OBRA].pdf
    date_obj: date do diário; suffix: opcional (ex: '_detalhado', '_sem_fotos').
    """
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
                'signatures',
                'signatures__signer',
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
            .order_by('activity__code', 'activity__name', 'pk')
            .all()
        )

        labor_by_type = {'I': {}, 'D': {}, 'T': {}}
        for wl in work_logs:
            for labor in wl.resources_labor.all():
                labor_type = labor.labor_type
                key = f"{labor.name or ''}_{labor.role or ''}_{labor.company or ''}"
                if labor_type in labor_by_type:
                    if key not in labor_by_type[labor_type]:
                        labor_by_type[labor_type][key] = {'labor': labor, 'count': 0}
                    labor_by_type[labor_type][key]['count'] += 1

        from core.utils.diary_equipment import aggregate_equipment_for_diary
        equipment_rows, total_equipment = aggregate_equipment_for_diary(diary, work_logs)

        total_indirect = sum(i['count'] for i in labor_by_type['I'].values())
        total_direct = sum(i['count'] for i in labor_by_type['D'].values())
        total_third_party = sum(i['count'] for i in labor_by_type['T'].values())
        total_labor = total_indirect + total_direct + total_third_party

        labor_entries_by_category = None
        try:
            entries = DiaryLaborEntry.objects.filter(diary=diary).select_related(
                'cargo', 'cargo__category'
            ).order_by('cargo__category__order', 'company', 'cargo__name')
            if entries.exists():
                labor_entries_by_category = {'indireta': [], 'direta': [], 'terceirizada': {}}
                for e in entries:
                    slug = e.cargo.category.slug
                    qty = _safe_int(e.quantity, 0)
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
        except Exception as exc:
            logger.debug(
                "Efetivo por DiaryLaborEntry indisponível; usando agregado por work logs: %s",
                exc,
                exc_info=True,
            )

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
                total_equipment=total_equipment,
                equipment_rows=equipment_rows,
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
        equipment_rows: List[Dict[str, Any]],
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
            LongTable,
            TableStyle,
            Image as RLImage,
        )
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_CENTER

        # Margens leves e proporcionais para dar respiro visual sem perder área útil.
        doc = SimpleDocTemplate(
            buffer_io,
            pagesize=A4,
            leftMargin=6 * mm,
            rightMargin=6 * mm,
            topMargin=6 * mm,
            # Rodapé fixo é desenhado em ~10-14 mm; margem maior evita sobreposição.
            bottomMargin=18 * mm,
        )
        content_width = doc.width
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
            spaceBefore=6,
            spaceAfter=3,
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
        # Lista de atividades: mais compacta que o corpo geral (muitas linhas sem dominar a página)
        activity_item_style = ParagraphStyle(
            name='ActivityItem',
            parent=styles['Normal'],
            fontSize=8,
            alignment=TA_LEFT,
            textColor=COLOR_TEXT,
            spaceAfter=0,
            leading=10,
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
        total_col_style = ParagraphStyle(
            name='TotalCol',
            parent=normal_style,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
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
            "<font color='#1A3A5C' size='14'><b>RELATÓRIO DIÁRIO DE OBRA</b></font>",
            ParagraphStyle(
                name='H1',
                fontName='Helvetica-Bold',
                fontSize=14,
                leading=16,
                spaceAfter=2,
                alignment=TA_CENTER,
                textColor=COLOR_PRIMARY,
            ),
        )
        header_sub = Paragraph(
            "<font color='#1A3A5C' size='9'>RDO n° %s · Código %s · %s · %s</font>" % (
                report_num if report_num is not None else '—',
                _safe_pdf_text(proj.code or '—', default='—'),
                diary.date.strftime('%d/%m/%Y'),
                _safe_pdf_text(wd_pt, default='—'),
            ),
            ParagraphStyle(
                name='H2',
                fontName='Helvetica',
                fontSize=9,
                leading=11,
                alignment=TA_CENTER,
                textColor=COLOR_PRIMARY,
            ),
        )
        if logo_absolute_path and os.path.exists(logo_absolute_path):
            try:
                # Logo horizontal institucional (wordmark + ícone): caixa mais larga, altura contida
                max_logo_w = 4.8 * cm
                max_logo_h = 1.15 * cm
                logo_w = max_logo_w
                logo_h = max_logo_h

                # Mantém proporção real da logo para evitar deformação no PDF.
                try:
                    if PIL_AVAILABLE and Image:
                        with Image.open(logo_absolute_path) as pil_logo:
                            src_w, src_h = pil_logo.size
                    else:
                        from reportlab.lib.utils import ImageReader
                        src_w, src_h = ImageReader(logo_absolute_path).getSize()

                    if src_w and src_h:
                        scale = min(max_logo_w / float(src_w), max_logo_h / float(src_h))
                        logo_w = max(1.0 * cm, float(src_w) * scale)
                        logo_h = max(0.4 * cm, float(src_h) * scale)
                except Exception as logo_size_err:
                    logger.debug("Não foi possível medir logo para escala proporcional: %s", logo_size_err)

                logo_img = RLImage(logo_absolute_path, width=logo_w, height=logo_h)
                logo_col_w = 5.2 * cm
                text_col_w = max(content_width - (2 * logo_col_w), 1.0 * cm)
                right_spacer = Paragraph(" ", ParagraphStyle(name='HeaderSpacer', fontSize=1))
                text_block = Table(
                    [[header_title], [Spacer(1, 1.5)], [header_sub]],
                    colWidths=[text_col_w],
                    hAlign='CENTER',
                )
                text_block.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                    ('TOPPADDING', (0, 0), (-1, -1), 1),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
                ]))

                # 3 colunas: logo | texto centralizado | espaçador
                # Isso mantém o título no centro real da página.
                header_rows = [[logo_img, text_block, right_spacer]]
                col_widths = [logo_col_w, text_col_w, logo_col_w]
            except Exception:
                header_rows = [[header_title], [header_sub]]
                col_widths = [content_width]
        else:
            header_rows = [[header_title], [header_sub]]
            col_widths = [content_width]
        tbl_header = Table(header_rows, colWidths=col_widths, hAlign='CENTER')
        tbl_header.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EAF2FB')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))

        # Linha separadora e bloco de dados da obra (fundo preto)
        obra_line = Paragraph(
            "<font color='black' size='9'><b>OBRA:</b> %s</font>" % (_safe_pdf_text((proj.name or '—')[:50], default='—'),),
            ParagraphStyle(name='ObraH', fontName='Helvetica', fontSize=9, textColor=colors.black),
        )
        line2 = Paragraph(
            "<font color='black' size='8'><b>Contratante:</b> %s &nbsp;&nbsp; <b>Resp. Técnico:</b> %s</font>" % (
                _safe_pdf_text((contratante or '—')[:40], default='—'),
                _safe_pdf_text((resp_tec or '—')[:35], default='—'),
            ),
            ParagraphStyle(name='Line2', fontName='Helvetica', fontSize=8, textColor=colors.black),
        )
        line3 = Paragraph(
            "<font color='black' size='8'><b>Local:</b> %s</font>" % (_safe_pdf_text((endereco or '—')[:90], default='—')),
            ParagraphStyle(name='Line3', fontName='Helvetica', fontSize=8, textColor=colors.black),
        )
        line4 = Paragraph(
            "<font color='black' size='8'><b>Início:</b> %s &nbsp;&nbsp; <b>Término:</b> %s &nbsp;&nbsp; <b>Dias corridos:</b> %s</font>" % (
                start_d.strftime('%d/%m/%y') if start_d else '—',
                end_d.strftime('%d/%m/%y') if end_d else '—',
                str(days_elapsed) if days_elapsed is not None else '—',
            ),
            ParagraphStyle(name='Line4', fontName='Helvetica', fontSize=8, textColor=colors.black),
        )
        sep_row = Table([[Paragraph(' ', ParagraphStyle(name='Sep', fontSize=1))]], colWidths=[content_width], hAlign='CENTER')
        sep_row.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (0, 0), 1, COLOR_PRIMARY),
            ('BACKGROUND', (0, 0), (0, 0), colors.white),
            ('TOPPADDING', (0, 0), (0, 0), 4),
            ('BOTTOMPADDING', (0, 0), (0, 0), 4),
        ]))
        header_block2 = Table([
            [obra_line],
            [line2],
            [line3],
            [line4],
        ], colWidths=[content_width], hAlign='CENTER')
        header_block2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        header_wrapper = Table(
            [[tbl_header], [sep_row], [header_block2]],
            colWidths=[content_width],
            hAlign='CENTER',
        )
        header_wrapper.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(header_wrapper)
        story.append(Spacer(1, 0.28 * cm))

        # Atividades / Serviços — seção com borda esquerda; conteúdo em tabela aninhada (1 flowable por célula)
        act_title = Paragraph(
            "<font color='white'><b>ATIVIDADES / SERVIÇOS</b></font>",
            ParagraphStyle(name='SecTitle', fontName='Helvetica-Bold', fontSize=9.5, textColor=colors.white),
        )
        act_rows = [[act_title]]
        if work_logs:
            for wl in work_logs:
                text = _safe_pdf_text(
                    getattr(wl.activity, 'display_code_name', None)
                    or (getattr(wl.activity, 'name', '') or '—'),
                    default='—',
                )
                if getattr(wl, 'notes', None) and wl.notes.strip():
                    notes = _safe_pdf_text(wl.notes[:100].replace('\n', ' '), default='')
                    if notes:
                        text += " <i>(%s)</i>" % notes
                try:
                    stage_disp = wl.get_work_stage_display()
                except Exception:
                    stage_disp = ""
                if stage_disp:
                    text += " — <i>%s</i>" % _safe_pdf_text(stage_disp, default="")
                act_rows.append([Paragraph(text, activity_item_style)])
        else:
            act_rows.append([Paragraph("Nenhuma atividade registrada.", activity_item_style)])
        # Largura interna menor que a célula para evitar availWidth negativo no ReportLab (padding da célula)
        inner_width = content_width
        inner_act = LongTable(act_rows, colWidths=[inner_width], repeatRows=0, hAlign='CENTER')
        inner_act.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), COLOR_PRIMARY),
            ('TEXTCOLOR', (0, 0), (0, 0), colors.white),
            ('LINEBELOW', (0, 0), (0, 0), 0.4, COLOR_BORDER),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (0, 0), 5),
            ('BOTTOMPADDING', (0, 0), (0, 0), 5),
            ('TOPPADDING', (0, 1), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_ACCENT]),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(inner_act)
        story.append(Spacer(1, 0.12 * cm))

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
                    return _safe_pdf_text(n, default='—')
                if hasattr(lab, 'get_role_display') and callable(getattr(lab, 'get_role_display')):
                    return _safe_pdf_text(lab.get_role_display() or '—', default='—')
                return '—'
            col_i = [Paragraph('EFETIVO INDIRETO (LPLAN)', table_header_style)]
            indireta_rows = labor_entries_by_category.get('indireta', []) if labor_entries_by_category else []
            if not indireta_rows and labor_by_type.get('I'):
                for item in labor_by_type['I'].values():
                    col_i.append(Paragraph(_lab_name(item['labor']) + ': ' + str(item['count']), normal_style))
            else:
                for item in indireta_rows:
                    cargo_name = _safe_pdf_text(item.get('cargo_name') or '—', default='—')
                    col_i.append(Paragraph(cargo_name + ': ' + str(item['quantity']), normal_style))

            col_d = [Paragraph('EFETIVO DIRETO', table_header_style)]
            direta_rows = labor_entries_by_category.get('direta', []) if labor_entries_by_category else []
            if not direta_rows and labor_by_type.get('D'):
                for item in labor_by_type['D'].values():
                    col_d.append(Paragraph(_lab_name(item['labor']) + ': ' + str(item['count']), normal_style))
            else:
                for item in direta_rows:
                    cargo_name = _safe_pdf_text(item.get('cargo_name') or '—', default='—')
                    col_d.append(Paragraph(cargo_name + ': ' + str(item['quantity']), normal_style))

            col_t = [Paragraph('EFETIVO TERCEIROS', table_header_style)]
            terceiros_rows = []
            if labor_entries_by_category and labor_entries_by_category.get('terceirizada'):
                for block in labor_entries_by_category['terceirizada']:
                    for item in block['items']:
                        company = _safe_pdf_text(block.get('company') or '—', default='—')
                        cargo_name = _safe_pdf_text(item.get('cargo_name') or '', default='')
                        col_t.append(Paragraph(company + ' ' + cargo_name + ': ' + str(item['quantity']), normal_style))
            elif labor_by_type.get('T'):
                for item in labor_by_type['T'].values():
                    lab = item['labor']
                    company = _safe_pdf_text(getattr(lab, 'company', None) or '—', default='—')
                    col_t.append(Paragraph(company + ' ' + _lab_name(lab) + ': ' + str(item['count']), normal_style))

            n = max(len(col_i), len(col_d), len(col_t))
            empty = Paragraph(' ', normal_style)
            for i in range(len(col_i), n):
                col_i.append(empty)
            for i in range(len(col_d), n):
                col_d.append(empty)
            for i in range(len(col_t), n):
                col_t.append(empty)
            # Mantém os três totais na mesma linha para evitar confusão visual com o total geral.
            col_i.append(Paragraph('TOTAL: ' + str(total_indirect), total_col_style))
            col_d.append(Paragraph('TOTAL: ' + str(total_direct), total_col_style))
            col_t.append(Paragraph('TOTAL: ' + str(total_third_party), total_col_style))
            total_row_idx = n
            efetivo_data = [[col_i[r], col_d[r], col_t[r]] for r in range(n + 1)]
            col_w = content_width / 3.0
            t_efetivo = LongTable(efetivo_data, colWidths=[col_w, col_w, col_w], repeatRows=1, hAlign='CENTER')
            t_efetivo.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), COLOR_PRIMARY),
                ('BACKGROUND', (1, 0), (1, 0), COLOR_PRIMARY),
                ('BACKGROUND', (2, 0), (2, 0), COLOR_PRIMARY),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, COLOR_ACCENT]),
                ('BACKGROUND', (0, total_row_idx), (0, total_row_idx), COLOR_ACCENT),
                ('BACKGROUND', (1, total_row_idx), (1, total_row_idx), COLOR_ACCENT),
                ('BACKGROUND', (2, total_row_idx), (2, total_row_idx), COLOR_ACCENT),
                ('LINEABOVE', (0, total_row_idx), (2, total_row_idx), 0.5, COLOR_DIVIDER_STRONG),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(t_efetivo)
            story.append(Spacer(1, 0.12 * cm))
            total_row = Table([[Paragraph(
                "EFETIVO TOTAL GERAL: %s" % total_labor,
                ParagraphStyle(name='EfetivoTotal', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=TA_CENTER),
            )]], colWidths=[content_width], hAlign='CENTER')
            total_row.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), COLOR_PRIMARY),
                ('ALIGN', (0, 0), (-1, -1), 'CENTRE'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(total_row)
            story.append(Spacer(1, 0.25 * cm))

        # Equipamentos (ordem = primeira ocorrência no diário, igual agregação do formulário)
        if equipment_rows:
            total_eq_style = ParagraphStyle(
                name='TotalEquip',
                parent=normal_style,
                fontName='Helvetica-Bold',
                textColor=colors.white,
            )
            data = [[Paragraph('EQUIPAMENTOS', table_header_style), Paragraph('Qtd', table_header_style)]]
            for item in equipment_rows:
                eq = item['equipment']
                code = _safe_pdf_text(_decode_js_escaped_text(getattr(eq, 'code', '') or ''), default='')
                name = _safe_pdf_text(_decode_js_escaped_text(getattr(eq, 'name', '') or ''), default='Sem nome')
                label = f"{code} – {name}" if code else name
                data.append([
                    Paragraph(label, normal_style),
                    Paragraph(str(item['quantity']), normal_style),
                ])
            data.append([Paragraph('TOTAL', total_eq_style), Paragraph(str(total_equipment), total_eq_style)])
            # Equipamentos ponta a ponta: usa toda largura útil.
            qty_col_w = 2.6 * cm
            desc_col_w = max(content_width - qty_col_w, 1.0 * cm)
            # Evita repetição de cabeçalho da tabela em quebra de página.
            t_eq = LongTable(data, colWidths=[desc_col_w, qty_col_w], repeatRows=0, hAlign='CENTER')
            t_eq.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_ACCENT]),
                ('BACKGROUND', (0, len(data) - 1), (-1, len(data) - 1), COLOR_PRIMARY),
                ('TEXTCOLOR', (0, len(data) - 1), (-1, len(data) - 1), colors.white),
                ('TEXTCOLOR', (0, len(data) - 1), (0, len(data) - 1), colors.white),
                ('TEXTCOLOR', (1, len(data) - 1), (1, len(data) - 1), colors.white),
                ('FONTNAME', (0, len(data) - 1), (-1, len(data) - 1), 'Helvetica-Bold'),
            ]))
            story.append(t_eq)
            story.append(Spacer(1, 0.25 * cm))

        # Ocorrência de Chuvas (bloco visual com melhor proporção/legibilidade)
        weather_text_style = ParagraphStyle(
            name='WeatherText',
            parent=normal_style,
            fontSize=9,
            leading=11,
            spaceAfter=1,
        )
        weather_title_style = ParagraphStyle(
            name='WeatherTitle',
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=12,
            textColor=COLOR_PRIMARY,
        )
        rain_title_style = ParagraphStyle(
            name='RainTitle',
            parent=table_header_style,
            alignment=TA_LEFT,
            textColor=colors.white,
        )
        rain = getattr(diary, 'rain_occurrence', None)
        rain_obs_raw = (getattr(diary, 'rain_observations', None) or '').strip()
        weather_raw = (getattr(diary, 'weather_conditions', None) or '').strip()
        weather_text = ("%s %s" % (weather_raw, rain_obs_raw)).lower()
        has_rain_hint = any(
            token in weather_text for token in ('chuva', 'chuv', 'garoa', 'temporal', 'pluv')
        )
        has_pluviometric = getattr(diary, 'pluviometric_index', None) is not None
        rain_label = {'F': 'Fraca', 'M': 'Média', 'S': 'Forte'}.get(
            rain,
            'Informada em observações' if (rain_obs_raw or has_rain_hint or has_pluviometric) else 'Nenhuma',
        )
        text = "Intensidade da Chuva: %s" % rain_label
        if getattr(diary, 'pluviometric_index', None) is not None:
            text += " | Índice Pluviométrico: %s mm" % diary.pluviometric_index
        rain_rows = [[Paragraph('OCORRÊNCIA DE CHUVA', rain_title_style)]]
        rain_rows.append([Paragraph(text, weather_text_style)])
        if rain_obs_raw:
            rain_rows.append([Spacer(1, 0.04 * cm)])
            rain_rows.append([Paragraph(
                "OBSERVAÇÕES: %s" % _safe_pdf_multiline_text(rain_obs_raw, default='—', max_len=300),
                weather_text_style,
            )])
        elif has_rain_hint and weather_raw:
            rain_rows.append([Spacer(1, 0.04 * cm)])
            rain_rows.append([Paragraph(
                "REFERÊNCIA EM CONDIÇÕES CLIMÁTICAS: %s" % _safe_pdf_multiline_text(weather_raw, default='—', max_len=300),
                weather_text_style,
            )])
        rain_tbl = LongTable(rain_rows, colWidths=[content_width], repeatRows=0, hAlign='CENTER')
        rain_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), COLOR_PRIMARY),
            ('TEXTCOLOR', (0, 0), (0, 0), colors.white),
            ('LINEBELOW', (0, 0), (0, 0), 0.4, COLOR_BORDER),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (0, 0), 5),
            ('BOTTOMPADDING', (0, 0), (0, 0), 5),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_ACCENT]),
        ]))
        story.append(rain_tbl)
        story.append(Spacer(1, 0.14 * cm))

        # Condições climáticas detalhadas (quando preenchidas)
        weather_parts = []
        if getattr(diary, 'weather_conditions', None) and diary.weather_conditions.strip():
            weather_parts.append(Paragraph(
                "<b>Condições climáticas:</b> %s" % _safe_pdf_multiline_text(diary.weather_conditions, default='—', max_len=400),
                normal_style,
            ))
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
            weather_rows = [[Paragraph("<font color='white'><b>CONDIÇÕES CLIMÁTICAS DETALHADAS</b></font>", rain_title_style)]]
            for p in weather_parts:
                weather_rows.append([p])
            weather_tbl = LongTable(weather_rows, colWidths=[content_width], repeatRows=0, hAlign='CENTER')
            weather_tbl.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), COLOR_PRIMARY),
                ('TEXTCOLOR', (0, 0), (0, 0), colors.white),
                ('LINEBELOW', (0, 0), (0, 0), 0.4, COLOR_BORDER),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (0, 0), 5),
                ('BOTTOMPADDING', (0, 0), (0, 0), 5),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_ACCENT]),
            ]))
            story.append(weather_tbl)
            story.append(Spacer(1, 0.15 * cm))

        # Horas trabalhadas
        if getattr(diary, 'work_hours', None) is not None:
            story.append(Paragraph("<b>Horas trabalhadas:</b> %s h" % diary.work_hours, normal_style))
            story.append(Spacer(1, 0.1 * cm))

        # Acidentes, Paralisações, Riscos, Incidentes, Fiscalizações, DDS, Observações gerais (só se preenchidos)
        def _sec(title, value, max_len=1200):
            if not value or not str(value).strip():
                return
            story.append(Paragraph("<b>%s</b>" % _safe_pdf_text(title, default='—'), normal_style))
            story.append(Paragraph(_safe_pdf_multiline_text(value, default='—', max_len=max_len), normal_style))
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
            occ_text_style = ParagraphStyle(
                name='OccText',
                parent=normal_style,
                fontSize=9,
                leading=11,
                spaceAfter=1,
            )
            occ_title_style = ParagraphStyle(
                name='OccTitle',
                fontName='Helvetica-Bold',
                fontSize=10,
                leading=12,
                textColor=colors.white,
            )
            occ_title = Paragraph(
                "<font color='white'><b>OCORRÊNCIAS E OBSERVAÇÕES</b></font>",
                occ_title_style,
            )
            occ_rows = [[occ_title], [Spacer(1, 0.05 * cm)]]
            if occurrences:
                for occ in occurrences:
                    desc = getattr(occ, 'description', '') or ''
                    desc = _safe_pdf_multiline_text(desc, default='—', max_len=500)
                    tags = list(occ.tags.values_list('name', flat=True)[:5])
                    tag_str = _safe_pdf_text(' | '.join(tags), default='') if tags else ''
                    occ_rows.append([Paragraph(desc or '—', occ_text_style)])
                    if tag_str:
                        occ_rows.append([Paragraph("Tags: %s" % tag_str, occ_text_style)])
            if getattr(diary, 'deliberations', None) and diary.deliberations.strip():
                occ_rows.append([Spacer(1, 0.03 * cm)])
                occ_rows.append([Paragraph("<b>DELIBERAÇÕES:</b>", occ_text_style)])
                occ_rows.append([Paragraph(
                    _safe_pdf_multiline_text(diary.deliberations, default='—', max_len=1000),
                    occ_text_style,
                )])
            inner_width = content_width
            inner_occ = LongTable(occ_rows, colWidths=[inner_width], repeatRows=0, hAlign='CENTER')
            inner_occ.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), COLOR_PRIMARY),
                ('TEXTCOLOR', (0, 0), (0, 0), colors.white),
                ('LINEBELOW', (0, 0), (0, 0), 0.4, COLOR_BORDER),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (0, 0), 4),
                ('BOTTOMPADDING', (0, 0), (0, 0), 3),
                ('TOPPADDING', (0, 1), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 2),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_ACCENT]),
            ]))
            story.append(inner_occ)
            story.append(Spacer(1, 0.1 * cm))

        # Registro Fotográfico — tabela aninhada; incluir imagem só se o arquivo for válido (PIL)
        if pdf_type != 'no_photos':
            photo_title = Paragraph(
                "<font color='#1A3A5C'><b>REGISTRO FOTOGRÁFICO</b></font>",
                ParagraphStyle(name='PhotoTitle', fontName='Helvetica-Bold', fontSize=10, textColor=COLOR_PRIMARY),
            )
            # Fotos com largura dinâmica da área útil atual, preservando proporção.
            photo_col_w = (content_width - 0.2 * cm) / 2.0
            img_w = max(photo_col_w - 0.9 * cm, 4.5 * cm)
            img_h = img_w * 0.72
            story.append(photo_title)
            story.append(Spacer(1, 0.12 * cm))
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
                            "<i>%s</i>" % _safe_pdf_text(cap, default='Foto'),
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
                        cell_content = Table([[img_flowable], [cap_para]], colWidths=[photo_col_w - 0.2 * cm])
                        cell_content.setStyle(TableStyle([
                            ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                            ('BACKGROUND', (0, 0), (-1, -1), COLOR_SURFACE),
                            ('TOPPADDING', (0, 0), (-1, -1), 3),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ]))
                        row_cells.append(cell_content)
                    if len(row_cells) == 1:
                        row_cells.append(Paragraph(' ', ParagraphStyle(name='E2', fontSize=1)))
                    if row_cells:
                        photo_cells.append(row_cells)
                if photo_cells:
                    t_photo = LongTable(photo_cells, colWidths=[photo_col_w, photo_col_w], repeatRows=0, hAlign='CENTER')
                    t_photo.setStyle(TableStyle([
                        ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                        ('LEFTPADDING', (0, 0), (-1, -1), 4),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                        ('TOPPADDING', (0, 0), (-1, -1), 4),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ]))
                    story.append(t_photo)
                else:
                    story.append(Paragraph("Nenhum registro fotográfico.", label_style))
            else:
                story.append(Paragraph("Nenhum registro fotográfico.", label_style))
            story.append(Spacer(1, 0.2 * cm))

        # Assinatura — bloco único de responsável pelo preenchimento (nome + assinatura desenhada)
        story.append(Spacer(1, 0.4 * cm))
        insp = getattr(diary, 'inspection_responsible', None) and diary.inspection_responsible.strip()
        inspection_signature = (
            diary.signatures.filter(signature_type='inspection')
            .select_related('signer')
            .order_by('-signed_at')
            .first()
        )
        insp_name = insp
        if not insp_name and inspection_signature and inspection_signature.signer:
            insp_name = (
                inspection_signature.signer.get_full_name().strip()
                or inspection_signature.signer.username
            )
        if not insp_name and getattr(diary, 'created_by', None):
            insp_name = (
                (diary.created_by.get_full_name() or '').strip()
                or getattr(diary.created_by, 'username', None)
            )

        sig_style = ParagraphStyle(
            name='Sig',
            parent=normal_style,
            fontSize=9.5,
            fontName='Helvetica-Bold',
            textColor=COLOR_TEXT,
            alignment=TA_CENTER,
        )
        sig_cargo_style = ParagraphStyle(
            name='SigCargo',
            parent=normal_style,
            fontSize=8.5,
            textColor=COLOR_TEXT_SECONDARY,
            alignment=TA_CENTER,
        )
        sig_line_style = ParagraphStyle(name='SigLine', parent=normal_style, fontSize=8, textColor=COLOR_TEXT_SECONDARY, alignment=TA_CENTER)

        signature_image_flowable = None
        if inspection_signature and inspection_signature.signature_data:
            try:
                decoded = _decode_data_url_or_base64_image(inspection_signature.signature_data)
                if not decoded or len(decoded) > (2 * 1024 * 1024):
                    raise ValueError("Assinatura inválida ou excede tamanho máximo permitido.")
                signature_stream = BytesIO(decoded)

                max_sig_w = 6.2 * cm
                max_sig_h = 1.8 * cm
                sig_w = max_sig_w
                sig_h = max_sig_h

                if PIL_AVAILABLE and Image:
                    with Image.open(signature_stream) as sig_img:
                        if sig_img.mode not in ('RGB', 'RGBA'):
                            sig_img = sig_img.convert('RGBA')
                        sw, sh = sig_img.size
                        if sw and sh:
                            scale = min(max_sig_w / float(sw), max_sig_h / float(sh))
                            sig_w = max(2.0 * cm, float(sw) * scale)
                            sig_h = max(0.6 * cm, float(sh) * scale)
                        prepared = BytesIO()
                        sig_img.save(prepared, format='PNG')
                        prepared.seek(0)
                        signature_image_flowable = RLImage(prepared, width=sig_w, height=sig_h)
                else:
                    signature_stream.seek(0)
                    signature_image_flowable = RLImage(signature_stream, width=sig_w, height=sig_h)
            except Exception as sig_err:
                logger.debug("Não foi possível renderizar assinatura no PDF: %s", sig_err)

        def _sig_block(name, cargo, signature_img=None):
            line_t = Table([['']], colWidths=[7 * cm])
            line_t.setStyle(TableStyle([('LINEBELOW', (0, 0), (0, 0), 1, COLOR_TEXT_SECONDARY)]))
            rows = []
            if signature_img is not None:
                rows.append([signature_img])
            else:
                rows.append([Paragraph('Assinatura não disponível', sig_line_style)])
            rows.append([line_t])
            rows.extend([
                [Paragraph(_safe_pdf_text(name, default='_________________________'), sig_style)],
                [Paragraph(_safe_pdf_text(cargo, default=''), sig_cargo_style)],
            ])
            block = Table(rows, colWidths=[content_width])
            block.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            return block

        c1 = _sig_block(insp_name, "Responsável pelo preenchimento", signature_image_flowable)
        sig_table = Table([[c1]], colWidths=[content_width])
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
    