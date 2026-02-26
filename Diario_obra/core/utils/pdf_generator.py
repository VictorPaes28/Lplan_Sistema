"""
Módulo de Geração de PDF para Diário de Obra V2.0 - LPLAN

Implementa geração robusta de PDFs usando:
- WeasyPrint (preferencial em Linux/macOS - melhor qualidade, mais recursos CSS)
- xhtml2pdf (usado no Windows e como fallback - sem dependências nativas)

Recursos:
- Otimização de imagens para reduzir uso de memória
- Regras CSS para evitar quebras de página
- No Windows não tenta WeasyPrint (evita aviso de Cairo/GTK) e usa xhtml2pdf direto
"""
import os
import sys
from pathlib import Path
from typing import Optional, List
from io import BytesIO
from django.conf import settings
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from PIL import Image
import logging

logger = logging.getLogger(__name__)

# Importação opcional do WeasyPrint (não usado no Windows - evita aviso de libcairo/libgobject)
WEASYPRINT_AVAILABLE = False
HTML = None
CSS = None
FontConfiguration = None

# Importação opcional do xhtml2pdf (recomendado no Windows)
XHTML2PDF_AVAILABLE = False
pisa = None

# No Windows não importamos WeasyPrint (exige Cairo/GTK); usa só xhtml2pdf
if sys.platform != "win32":
    try:
        from weasyprint import HTML, CSS
        try:
            from weasyprint.text.fonts import FontConfiguration  # WeasyPrint 53+
        except ImportError:
            from weasyprint.fonts import FontConfiguration  # WeasyPrint 52.x (cPanel)
        WEASYPRINT_AVAILABLE = True
        logger.info("WeasyPrint disponível - será usado preferencialmente para geração de PDF")
    except Exception as e:
        WEASYPRINT_AVAILABLE = False
        logger.info("WeasyPrint não disponível - será usado xhtml2pdf se instalado.")

if not WEASYPRINT_AVAILABLE:
    class HTML:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("WeasyPrint não está disponível. Use xhtml2pdf: pip install xhtml2pdf")
    class CSS:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("WeasyPrint não está disponível.")
    class FontConfiguration:
        pass

# Tenta importar xhtml2pdf (fallback para Windows; dependências podem tentar carregar Cairo)
try:
    from xhtml2pdf import pisa
    XHTML2PDF_AVAILABLE = True
    if WEASYPRINT_AVAILABLE:
        logger.info("xhtml2pdf também disponível - será usado como fallback se necessário")
    else:
        logger.info("xhtml2pdf disponível - será usado para geração de PDF (WeasyPrint não disponível)")
except Exception as e:
    # ImportError, OSError (Cairo/lib não encontrada em dependências como svglib), etc.
    XHTML2PDF_AVAILABLE = False
    if not WEASYPRINT_AVAILABLE:
        logger.warning("xhtml2pdf não disponível (%s). Instale: pip install xhtml2pdf", str(e)[:100])


class ImageOptimizer:
    """
    Classe para otimização de imagens para geração de PDF.
    
    Redimensiona imagens para max-width 800px, converte para JPEG
    (qualidade 80%, RGB) e remove dados EXIF para evitar bugs de rotação.
    """
    
    MAX_WIDTH = 800
    JPEG_QUALITY = 80
    
    @classmethod
    def optimize_image_for_pdf(
        cls,
        image_path: str,
        output_path: Optional[str] = None
    ) -> str:
        """
        Otimiza uma imagem para inclusão em PDF.
        
        Processo:
        1. Abre a imagem original
        2. Converte para RGB (se necessário)
        3. Redimensiona mantendo proporção (max-width 800px)
        4. Remove dados EXIF
        5. Salva como JPEG com qualidade 80%
        
        Args:
            image_path: Caminho absoluto para a imagem original
            output_path: Caminho opcional para salvar a imagem otimizada.
                        Se None, cria um arquivo temporário.
        
        Returns:
            str: Caminho absoluto da imagem otimizada
        """
        try:
            # Abre a imagem original
            with Image.open(image_path) as img:
                # Converte para RGB se necessário (remove canal alpha se existir)
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Cria fundo branco para imagens com transparência
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = rgb_img
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Calcula novo tamanho mantendo proporção
                width, height = img.size
                if width > cls.MAX_WIDTH:
                    ratio = cls.MAX_WIDTH / width
                    new_width = cls.MAX_WIDTH
                    new_height = int(height * ratio)
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Determina caminho de saída
                if output_path is None:
                    # Cria arquivo temporário no mesmo diretório
                    base_path = Path(image_path)
                    output_path = str(base_path.parent / f"{base_path.stem}_pdf_opt.jpg")
                
                # Salva como JPEG sem dados EXIF
                img.save(
                    output_path,
                    'JPEG',
                    quality=cls.JPEG_QUALITY,
                    optimize=True,
                    exif=b''  # Remove dados EXIF
                )
                
                logger.info(f"Imagem otimizada: {image_path} -> {output_path}")
                return output_path
                
        except Exception as e:
            logger.error(f"Erro ao otimizar imagem {image_path}: {e}")
            # Em caso de erro, retorna o caminho original
            return image_path
    
    @classmethod
    def get_optimized_image_path(cls, image_field) -> Optional[str]:
        """
        Retorna o caminho da imagem otimizada se existir, caso contrário
        otimiza e retorna o caminho.
        
        Args:
            image_field: Campo ImageField do modelo DiaryImage
        
        Returns:
            str: Caminho absoluto da imagem otimizada ou None se não houver imagem
        """
        if not image_field or not image_field.name:
            return None
        
        # Verifica se já existe versão otimizada
        if hasattr(image_field.instance, 'pdf_optimized') and image_field.instance.pdf_optimized:
            optimized_path = image_field.instance.pdf_optimized.path
            if os.path.exists(optimized_path):
                return optimized_path
        
        # Se não existe, otimiza a imagem original
        original_path = image_field.path
        if not os.path.exists(original_path):
            return None
        
        # Otimiza e salva no campo pdf_optimized
        optimized_path = cls.optimize_image_for_pdf(original_path)
        
        # Atualiza o campo pdf_optimized do modelo (se existir)
        if hasattr(image_field.instance, 'pdf_optimized'):
            with open(optimized_path, 'rb') as f:
                image_field.instance.pdf_optimized.save(
                    os.path.basename(optimized_path),
                    ContentFile(f.read()),
                    save=False
                )
        
        return optimized_path


class PDFGenerator:
    """
    Classe principal para geração de PDFs de Diários de Obra.
    
    Usa WeasyPrint com:
    - Caminhos de arquivo locais (file://) em vez de URLs HTTP
    - Regras CSS para evitar quebras de página
    - Otimização de imagens pré-processada
    """
    
    @staticmethod
    def generate_diary_pdf(
        diary_id: int,
        output_path: Optional[str] = None,
        pdf_type: str = 'normal'
    ) -> BytesIO:
        """
        Gera PDF de um Diário de Obra.
        
        Args:
            diary_id: ID do ConstructionDiary
            output_path: Caminho opcional para salvar o PDF. Se None, retorna BytesIO.
        
        Returns:
            BytesIO: Conteúdo do PDF em memória ou salva em arquivo
        
        Raises:
            ConstructionDiary.DoesNotExist: Se o diário não existir
        """
        from core.models import ConstructionDiary, DiaryImage
        
        try:
            diary = ConstructionDiary.objects.select_related(
                'project',
                'created_by',
                'reviewed_by'
            ).prefetch_related(
                'images',
                'videos',
                'attachments',
                'work_logs__activity',
                'occurrences',
                'occurrences__tags',
            ).get(pk=diary_id)
        except ConstructionDiary.DoesNotExist:
            raise ConstructionDiary.DoesNotExist(
                f"Diário com ID {diary_id} não encontrado."
            )
        
        # Filtra imagens baseado no tipo de PDF
        if pdf_type == 'no_photos':
            images = diary.images.none()  # Sem fotos
        else:
            images = diary.images.filter(is_approved_for_report=True).order_by('uploaded_at')
        
        # Prepara imagens com caminhos
        # Para WeasyPrint: file:// URIs
        # Para xhtml2pdf: caminhos absolutos
        images_with_paths = []
        for image in images:
            image_path = None
            image_absolute_path = None
            
            if image.pdf_optimized and os.path.exists(image.pdf_optimized.path):
                image_path = Path(image.pdf_optimized.path).as_uri()  # Para WeasyPrint
                image_absolute_path = image.pdf_optimized.path  # Para xhtml2pdf
            elif image.image and os.path.exists(image.image.path):
                # Se não existe otimizada, otimiza agora
                optimized_path = ImageOptimizer.get_optimized_image_path(image.image)
                if optimized_path and os.path.exists(optimized_path):
                    image_path = Path(optimized_path).as_uri()  # Para WeasyPrint
                    image_absolute_path = optimized_path  # Para xhtml2pdf
            
            images_with_paths.append({
                'image': image,
                'file_url': image_path or '',  # file:// URI para WeasyPrint
                'absolute_path': image_absolute_path or '',  # Caminho absoluto para xhtml2pdf
            })
        
        # Prepara work_logs com relacionamentos
        work_logs = diary.work_logs.select_related('activity').prefetch_related(
            'resources_labor',
            'resources_equipment'
        ).all()
        
        # Agrupa mão de obra por tipo e nome (para contar corretamente)
        labor_by_type = {
            'I': {},  # Indireto
            'D': {},  # Direto
            'T': {},  # Terceiros
        }
        
        # Agrupa equipamentos por nome (para contar corretamente)
        equipment_count = {}
        
        for work_log in work_logs:
            # Conta mão de obra por tipo e nome
            for labor in work_log.resources_labor.all():
                labor_type = labor.labor_type
                # Cria chave única: nome + role + company
                labor_key = f"{labor.name or ''}_{labor.role or ''}_{labor.company or ''}"
                
                if labor_type == 'I':
                    if labor_key not in labor_by_type['I']:
                        labor_by_type['I'][labor_key] = {
                            'labor': labor,
                            'count': 0
                        }
                    labor_by_type['I'][labor_key]['count'] += 1
                elif labor_type == 'D':
                    if labor_key not in labor_by_type['D']:
                        labor_by_type['D'][labor_key] = {
                            'labor': labor,
                            'count': 0
                        }
                    labor_by_type['D'][labor_key]['count'] += 1
                elif labor_type == 'T':
                    if labor_key not in labor_by_type['T']:
                        labor_by_type['T'][labor_key] = {
                            'labor': labor,
                            'count': 0
                        }
                    labor_by_type['T'][labor_key]['count'] += 1
            
            # Conta equipamentos por nome
            for equipment in work_log.resources_equipment.all():
                equipment_key = f"{equipment.code}_{equipment.name}"
                if equipment_key not in equipment_count:
                    equipment_count[equipment_key] = {
                        'equipment': equipment,
                        'count': 0
                    }
                equipment_count[equipment_key]['count'] += 1
        
        # Calcula totais (legado: work_log.resources_labor)
        total_indirect = sum(item['count'] for item in labor_by_type['I'].values())
        total_direct = sum(item['count'] for item in labor_by_type['D'].values())
        total_third_party = sum(item['count'] for item in labor_by_type['T'].values())
        total_labor = total_indirect + total_direct + total_third_party

        # Mão de obra por categorias (DiaryLaborEntry) - preferência quando existir
        labor_entries_by_category = None
        try:
            from core.models import DiaryLaborEntry
            entries = DiaryLaborEntry.objects.filter(diary=diary).select_related(
                'cargo', 'cargo__category'
            ).order_by('cargo__category__order', 'company', 'cargo__name')
            if entries.exists():
                labor_entries_by_category = {'indireta': [], 'direta': [], 'terceirizada': {}}
                for e in entries:
                    slug = e.cargo.category.slug
                    item = {'cargo_name': e.cargo.name, 'quantity': e.quantity}
                    if slug == 'terceirizada':
                        company = e.company or '(Sem empresa)'
                        if company not in labor_entries_by_category['terceirizada']:
                            labor_entries_by_category['terceirizada'][company] = []
                        labor_entries_by_category['terceirizada'][company].append(item)
                    elif slug in labor_entries_by_category:
                        labor_entries_by_category[slug].append(item)
                labor_entries_by_category['terceirizada'] = [
                    {'company': k, 'items': v} for k, v in labor_entries_by_category['terceirizada'].items()
                ]
                total_indirect = sum(e['quantity'] for e in labor_entries_by_category['indireta'])
                total_direct = sum(e['quantity'] for e in labor_entries_by_category['direta'])
                total_third_party = sum(
                    item['quantity'] for block in labor_entries_by_category['terceirizada'] for item in block['items']
                )
                total_labor = total_indirect + total_direct + total_third_party
        except Exception:
            pass

        total_equipment = sum(item['count'] for item in equipment_count.values())
        
        # Calcula dias corridos e restantes
        days_elapsed = None
        days_remaining = None
        if diary.project.start_date and diary.project.end_date:
            from datetime import date
            if diary.date >= diary.project.start_date:
                delta = diary.date - diary.project.start_date
                days_elapsed = delta.days
            if diary.date <= diary.project.end_date:
                delta = diary.project.end_date - diary.date
                days_remaining = delta.days
        
        # Prepara caminho da logo LPLAN (procura em vários formatos)
        logo_path = None
        logo_absolute_path = None
        logo_file_url = None
        
        # Tenta encontrar a logo em diferentes formatos
        logo_formats = ['lplan_logo.png', 'lplan_logo.jpg', 'lplan_logo.jpeg', 'lplan_logo.svg']
        logo_static_dir = Path(settings.BASE_DIR) / 'core' / 'static' / 'core' / 'images'
        
        for logo_filename in logo_formats:
            logo_static_path = logo_static_dir / logo_filename
            if logo_static_path.exists():
                logo_absolute_path = str(logo_static_path)
                logo_file_url = Path(logo_absolute_path).as_uri()
                logo_path = logo_file_url
                break
        
        # Prepara vídeos com thumbnails
        videos_with_paths = []
        if pdf_type != 'no_photos':
            videos = diary.videos.filter(is_approved_for_report=True).order_by('uploaded_at')
            for video in videos:
                thumbnail_path = None
                thumbnail_absolute_path = None
                
                if video.thumbnail and os.path.exists(video.thumbnail.path):
                    thumbnail_path = Path(video.thumbnail.path).as_uri()
                    thumbnail_absolute_path = video.thumbnail.path
                
                videos_with_paths.append({
                    'video': video,
                    'thumbnail_url': thumbnail_path or '',
                    'thumbnail_absolute_path': thumbnail_absolute_path or '',
                })
        
        # Prepara anexos
        attachments = []
        if hasattr(diary, 'attachments'):
            attachments = diary.attachments.all().order_by('uploaded_at')
        
        # Ocorrências do diário (modelo DiaryOccurrence)
        occurrences = list(diary.occurrences.select_related('created_by').prefetch_related('tags').order_by('created_at'))

        # Prepara contexto para template
        context = {
            'diary': diary,
            'images_with_paths': images_with_paths,
            'videos_with_paths': videos_with_paths,
            'attachments': attachments,
            'occurrences': occurrences,
            'project': diary.project,
            'work_logs': work_logs,
            'labor_by_type': labor_by_type,  # Dados agrupados de mão de obra (legado)
            'labor_entries_by_category': labor_entries_by_category,  # Novo: por categorias/cargos
            'equipment_count': equipment_count,  # Dados agrupados de equipamentos
            'total_indirect': total_indirect,
            'total_direct': total_direct,
            'total_third_party': total_third_party,
            'total_labor': total_labor,
            'total_equipment': total_equipment,
            'days_elapsed': days_elapsed,
            'days_remaining': days_remaining,
            'logo_path': logo_path,
            'logo_absolute_path': logo_absolute_path,
        }
        
        # Renderiza template HTML
        html_string = render_to_string('core/pdf_template.html', context)
        
        # Gera PDF usando WeasyPrint (preferencial) ou xhtml2pdf (fallback)
        if WEASYPRINT_AVAILABLE:
            # Usa WeasyPrint (melhor qualidade, mais recursos CSS)
            font_config = FontConfiguration()
            css_string = PDFGenerator._get_print_css()
            
            html = HTML(string=html_string, base_url=settings.MEDIA_ROOT)
            css = CSS(string=css_string)
            
            if output_path:
                html.write_pdf(output_path, stylesheets=[css], font_config=font_config)
                logger.info(f"PDF gerado com WeasyPrint: {output_path}")
                return None
            else:
                pdf_bytes = html.write_pdf(stylesheets=[css], font_config=font_config)
                return BytesIO(pdf_bytes)
        
        elif XHTML2PDF_AVAILABLE:
            # Usa xhtml2pdf como alternativa (funciona no Windows sem dependências)
            logger.info("Gerando PDF com xhtml2pdf (alternativa)")
            
            # Prepara contexto com caminhos absolutos para xhtml2pdf
            context_xhtml2pdf = {
                'diary': diary,
                'images_with_paths': [
                    {
                        'image': img['image'],
                        'file_url': img['absolute_path'] or img['file_url'],  # Usa caminho absoluto
                    }
                    for img in images_with_paths
                ],
                'videos_with_paths': [
                    {
                        'video': vid['video'],
                        'thumbnail_url': vid['thumbnail_absolute_path'] or vid['thumbnail_url'],
                    }
                    for vid in videos_with_paths
                ],
                'attachments': attachments,
                'occurrences': occurrences,
                'project': diary.project,
                'work_logs': work_logs,
                'total_indirect': total_indirect,
                'total_direct': total_direct,
                'total_third_party': total_third_party,
                'total_labor': total_labor,
                'total_equipment': total_equipment,
                'days_elapsed': days_elapsed,
                'days_remaining': days_remaining,
                'logo_path': logo_absolute_path or logo_path,  # Para xhtml2pdf usa caminho absoluto
                'logo_absolute_path': logo_absolute_path,
            }
            
            # Renderiza template HTML com caminhos absolutos
            html_string = render_to_string('core/pdf_template.html', context_xhtml2pdf)
            
            # Converte file:// URIs restantes para caminhos absolutos (se houver)
            html_string = PDFGenerator._convert_file_uris_to_paths(html_string)
            
            pdf_bytes = BytesIO()
            result = pisa.CreatePDF(
                html_string,
                dest=pdf_bytes,
                encoding='utf-8'
            )
            
            if result.err:
                raise RuntimeError(f"Erro ao gerar PDF com xhtml2pdf: {result.err}")
            
            if output_path:
                with open(output_path, 'wb') as f:
                    f.write(pdf_bytes.getvalue())
                logger.info(f"PDF gerado com xhtml2pdf: {output_path}")
                return None
            else:
                pdf_bytes.seek(0)
                return pdf_bytes
        
        else:
            raise RuntimeError(
                "Nenhuma biblioteca de PDF disponível. "
                "Instale WeasyPrint (pip install weasyprint) ou xhtml2pdf (pip install xhtml2pdf)."
            )
    
    
    @staticmethod
    def _get_print_css() -> str:
        """
        Retorna CSS customizado para impressão com regras de quebra de página.
        
        Regras críticas:
        - page-break-inside: avoid no contêiner .image-card
        - Margens e espaçamento adequados
        - Tipografia otimizada para impressão
        """
        return """
        @page {
            size: A4;
            margin: 2cm;
        }
        
        body {
            font-family: 'Arial', 'Helvetica', sans-serif;
            font-size: 10pt;
            line-height: 1.4;
            color: #333;
        }
        
        .header {
            border-bottom: 2px solid #333;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        
        .header h1 {
            margin: 0;
            font-size: 18pt;
            color: #000;
        }
        
        .header .project-info {
            font-size: 9pt;
            color: #666;
            margin-top: 5px;
        }
        
        .diary-info {
            margin-bottom: 20px;
            padding: 10px;
            background-color: #f5f5f5;
            border-radius: 4px;
        }
        
        .diary-info table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .diary-info td {
            padding: 5px;
            font-size: 9pt;
        }
        
        .diary-info td:first-child {
            font-weight: bold;
            width: 30%;
        }
        
        .images-section {
            margin-top: 30px;
        }
        
        .images-section h2 {
            font-size: 14pt;
            border-bottom: 1px solid #ccc;
            padding-bottom: 5px;
            margin-bottom: 15px;
        }
        
        .image-card {
            margin-bottom: 20px;
            page-break-inside: avoid;
            break-inside: avoid;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 10px;
            background-color: #fff;
        }
        
        .image-card img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 0 auto 10px;
            border-radius: 4px;
        }
        
        .image-caption {
            font-size: 9pt;
            color: #666;
            text-align: center;
            font-style: italic;
            padding: 5px;
        }
        
        .work-logs-section {
            margin-top: 30px;
        }
        
        .work-logs-section h2 {
            font-size: 14pt;
            border-bottom: 1px solid #ccc;
            padding-bottom: 5px;
            margin-bottom: 15px;
        }
        
        .work-log-item {
            margin-bottom: 15px;
            padding: 10px;
            border-left: 3px solid #007bff;
            background-color: #f8f9fa;
            page-break-inside: avoid;
            break-inside: avoid;
        }
        
        .work-log-item h3 {
            font-size: 11pt;
            margin: 0 0 5px 0;
            color: #007bff;
        }
        
        .work-log-item .activity-code {
            font-weight: bold;
            color: #000;
        }
        
        .work-log-item .progress-info {
            font-size: 9pt;
            color: #666;
            margin-top: 5px;
        }
        
        .notes-section {
            margin-top: 10px;
            padding: 10px;
            background-color: #fff;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        
        .notes-section h4 {
            font-size: 10pt;
            margin: 0 0 5px 0;
            color: #333;
        }
        
        .notes-section p {
            font-size: 9pt;
            margin: 0;
            color: #666;
        }
        
        .footer {
            margin-top: 30px;
            padding-top: 10px;
            border-top: 1px solid #ccc;
            font-size: 8pt;
            color: #999;
            text-align: center;
        }
        
        /* Evita quebra de página em elementos críticos */
        .no-break {
            page-break-inside: avoid;
            break-inside: avoid;
        }
        """
    
    @staticmethod
    def _convert_file_uris_to_paths(html_string: str) -> str:
        """
        Converte URIs file:// para caminhos absolutos para xhtml2pdf.
        xhtml2pdf não suporta file:// URIs, precisa de caminhos absolutos.
        """
        import re
        from urllib.parse import unquote
        
        def replace_file_uri(match):
            file_uri = match.group(1)
            # Remove file:// e decodifica
            if file_uri.startswith('file:///'):
                # Windows: file:///C:/path
                path = unquote(file_uri[8:])
            elif file_uri.startswith('file://'):
                # Unix: file:///path
                path = unquote(file_uri[7:])
            else:
                return match.group(0)
            
            # Converte para caminho absoluto
            return f'src="{path}"'
        
        # Substitui file:// URIs em tags img
        html_string = re.sub(r'src="(file://[^"]+)"', replace_file_uri, html_string)
        
        return html_string

