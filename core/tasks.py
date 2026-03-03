"""
Tarefas Celery para Diário de Obra V2.0.

Tarefas assíncronas para processamento pesado:
- Geração de PDFs de diários de obra
- Otimização em lote de imagens
"""
import os
from pathlib import Path
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import logging

logger = logging.getLogger(__name__)

# Importação opcional do Celery
try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    # Fallback se Celery não estiver instalado
    CELERY_AVAILABLE = False
    def shared_task(*args, **kwargs):
        """Decorator dummy quando Celery não está disponível."""
        def decorator(func):
            return func
        return decorator


@shared_task(bind=True, max_retries=3)
def generate_diary_pdf_task(self, diary_id: int, output_filename: str = None):
    """
    Tarefa assíncrona para gerar PDF de um Diário de Obra.
    
    Nota: Esta função só funciona se Celery estiver instalado e configurado.
    """
    if not CELERY_AVAILABLE:
        logger.warning("Celery não está disponível. Use geração síncrona.")
        return None
    """
    Tarefa assíncrona para gerar PDF de um Diário de Obra.
    
    Esta tarefa:
    1. Gera o PDF usando PDFGenerator
    2. Salva o arquivo no storage configurado
    3. Retorna o caminho do arquivo gerado
    
    Args:
        diary_id: ID do ConstructionDiary
        output_filename: Nome opcional do arquivo de saída.
                        Se None, gera nome baseado no diário.
    
    Returns:
        str: Caminho do arquivo PDF gerado
    
    Raises:
        Retry: Se houver erro, tenta novamente até max_retries
    """
    try:
        from core.utils.pdf_generator import PDFGenerator
        from core.models import ConstructionDiary
        
        # Verifica se o diário existe
        try:
            diary = ConstructionDiary.objects.get(pk=diary_id)
        except ConstructionDiary.DoesNotExist:
            logger.error(f"Diário {diary_id} não encontrado para geração de PDF")
            raise
        
        # Gera nome do arquivo se não fornecido
        if output_filename is None:
            output_filename = f"diario_{diary.project.code}_{diary.date.strftime('%Y%m%d')}.pdf"
        
        # Cria diretório de saída se não existir
        output_dir = Path(settings.MEDIA_ROOT) / 'pdfs' / str(diary.date.year) / str(diary.date.month)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / output_filename
        
        # Gera PDF
        pdf_bytes = PDFGenerator.generate_diary_pdf(diary_id)
        
        if pdf_bytes:
            # Salva o PDF
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes.getvalue())
            
            logger.info(f"PDF gerado com sucesso: {output_path}")
            
            # Retorna URL relativa para acesso
            relative_path = output_path.relative_to(settings.MEDIA_ROOT)
            return str(relative_path)
        else:
            raise Exception("Falha ao gerar PDF: BytesIO vazio")
            
    except Exception as exc:
        logger.error(f"Erro ao gerar PDF do diário {diary_id}: {exc}")
        # Retry com backoff exponencial
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task
def optimize_diary_images_task(diary_id: int):
    """
    Tarefa assíncrona para otimizar todas as imagens de um diário.
    
    Útil para processar em lote imagens que foram carregadas antes
    da implementação da otimização automática.
    
    Args:
        diary_id: ID do ConstructionDiary
    
    Returns:
        int: Número de imagens otimizadas
    """
    try:
        from core.models import ConstructionDiary, DiaryImage
        from core.utils.pdf_generator import ImageOptimizer
        
        try:
            diary = ConstructionDiary.objects.get(pk=diary_id)
        except ConstructionDiary.DoesNotExist:
            logger.error(f"Diário {diary_id} não encontrado")
            return 0
        
        images = DiaryImage.objects.filter(diary=diary)
        optimized_count = 0
        
        for image in images:
            if image.image and image.image.name:
                try:
                    # Verifica se já existe versão otimizada
                    if image.pdf_optimized and os.path.exists(image.pdf_optimized.path):
                        continue
                    
                    # Otimiza imagem
                    original_path = image.image.path
                    if os.path.exists(original_path):
                        optimized_path = ImageOptimizer.optimize_image_for_pdf(original_path)
                        
                        if optimized_path and os.path.exists(optimized_path):
                            # Salva no campo pdf_optimized
                            with open(optimized_path, 'rb') as f:
                                from django.core.files.base import ContentFile
                                image.pdf_optimized.save(
                                    os.path.basename(optimized_path),
                                    ContentFile(f.read()),
                                    save=True
                                )
                            optimized_count += 1
                            logger.info(f"Imagem {image.id} otimizada com sucesso")
                except Exception as e:
                    logger.error(f"Erro ao otimizar imagem {image.id}: {e}")
                    continue
        
        logger.info(f"Otimização concluída: {optimized_count} imagens processadas para diário {diary_id}")
        return optimized_count
        
    except Exception as e:
        logger.error(f"Erro na tarefa de otimização de imagens: {e}")
        return 0

