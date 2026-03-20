"""
Validações de segurança para uploads de arquivo.
"""
import os
import re
from io import BytesIO
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
import logging

logger = logging.getLogger(__name__)

# Limites de tamanho (em bytes)
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB
MAX_ATTACHMENT_SIZE = 50 * 1024 * 1024  # 50MB

# Tipos MIME permitidos
ALLOWED_IMAGE_TYPES = [
    'image/jpeg',
    'image/jpg',
    'image/png',
    'image/gif',
    'image/webp',
]

ALLOWED_VIDEO_TYPES = [
    'video/mp4',
    'video/mpeg',
    'video/quicktime',  # MOV
    'video/x-msvideo',  # AVI
    'video/x-matroska',  # MKV
    'video/webm',
]

ALLOWED_ATTACHMENT_TYPES = [
    'application/pdf',
    'application/msword',  # .doc
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
    'application/vnd.ms-excel',  # .xls
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
    'text/plain',
    'application/zip',
    'application/x-rar-compressed',
] + ALLOWED_IMAGE_TYPES + ALLOWED_VIDEO_TYPES  # Permite imagens e vídeos como anexos também

# Extensões permitidas (validação adicional)
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
ALLOWED_VIDEO_EXTENSIONS = ['.mp4', '.mpeg', '.mov', '.avi', '.mkv', '.webm']
ALLOWED_ATTACHMENT_EXTENSIONS = [
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.zip', '.rar'
] + ALLOWED_IMAGE_EXTENSIONS + ALLOWED_VIDEO_EXTENSIONS

HEIC_IMAGE_TYPES = {
    'image/heic',
    'image/heif',
    'image/heic-sequence',
    'image/heif-sequence',
}
HEIC_EXTENSIONS = {'.heic', '.heif'}


def sanitize_filename(filename):
    """
    Sanitiza nome de arquivo para prevenir path traversal e caracteres perigosos.
    
    Args:
        filename: Nome do arquivo original
        
    Returns:
        str: Nome do arquivo sanitizado
    """
    if not filename:
        return 'arquivo'
    
    # Remove path components perigosos
    filename = os.path.basename(filename)
    
    # Remove caracteres perigosos
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)
    
    # Remove espaços múltiplos
    filename = re.sub(r'\s+', '_', filename)
    
    # Limita tamanho do nome
    name, ext = os.path.splitext(filename)
    if len(name) > 100:
        name = name[:100]
    filename = name + ext
    
    # Se ficou vazio, usa nome padrão
    if not filename or filename == ext:
        filename = 'arquivo' + (ext if ext else '')
    
    # Evita path traversal: nunca retornar apenas . ou .. ou sequência de pontos
    if filename in ('.', '..') or filename.strip('.') == '':
        filename = 'arquivo' + (ext if ext else '')
    
    return filename


def normalize_uploaded_image(file):
    """
    Converte uploads HEIC/HEIF para JPEG para compatibilidade com Pillow/PDF.

    Retorna o próprio arquivo quando não é HEIC/HEIF.
    """
    if not file:
        return file

    filename = getattr(file, 'name', '') or ''
    ext = os.path.splitext(filename.lower())[1]
    content_type = (getattr(file, 'content_type', '') or '').lower()
    is_heic = ext in HEIC_EXTENSIONS or content_type in HEIC_IMAGE_TYPES

    if not is_heic:
        return file

    try:
        from PIL import Image
    except ImportError as exc:
        raise ValidationError(
            'Não foi possível processar imagem HEIC: Pillow não está disponível no servidor.'
        ) from exc

    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    except Exception as exc:
        raise ValidationError(
            'Imagem HEIC/HEIF detectada, mas o servidor não possui suporte de conversão. '
            'Instale "pillow-heif" para conversão automática ou envie em JPG/PNG.'
        ) from exc

    try:
        file.seek(0)
        source_bytes = file.read()
        file.seek(0)
        img = Image.open(BytesIO(source_bytes))
        if img.mode != 'RGB':
            img = img.convert('RGB')

        output = BytesIO()
        img.save(output, format='JPEG', quality=90, optimize=True)
        output.seek(0)

        base_name = os.path.splitext(os.path.basename(filename or 'imagem'))[0]
        new_name = sanitize_filename(f'{base_name}.jpg')
        converted = InMemoryUploadedFile(
            file=output,
            field_name=getattr(file, 'field_name', None),
            name=new_name,
            content_type='image/jpeg',
            size=output.getbuffer().nbytes,
            charset=getattr(file, 'charset', None),
        )
        logger.info("Imagem convertida HEIC/HEIF -> JPEG: %s -> %s", filename, new_name)
        return converted
    except ValidationError:
        raise
    except Exception as exc:
        logger.exception("Falha ao converter imagem HEIC/HEIF: %s", filename)
        raise ValidationError(
            'Não foi possível converter a imagem HEIC/HEIF. Tente reenviar em JPG/PNG.'
        ) from exc


def validate_image_file(file, max_size=MAX_IMAGE_SIZE):
    """
    Valida arquivo de imagem.
    
    Args:
        file: Arquivo Django UploadedFile
        max_size: Tamanho máximo em bytes (padrão: 10MB)
        
    Raises:
        ValidationError: Se o arquivo não for válido
    """
    if not file:
        raise ValidationError('Nenhum arquivo fornecido.')
    
    # Normaliza HEIC/HEIF antes das demais validações
    file = normalize_uploaded_image(file)

    # Valida tamanho
    if hasattr(file, 'size') and file.size > max_size:
        size_mb = max_size / (1024 * 1024)
        raise ValidationError(f'O arquivo é muito grande. Tamanho máximo permitido: {size_mb}MB.')
    
    # Valida tipo MIME
    content_type = getattr(file, 'content_type', None)
    if content_type and content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError(f'Tipo de arquivo não permitido: {content_type}. Tipos permitidos: {", ".join(ALLOWED_IMAGE_TYPES)}')
    
    # Valida extensão
    filename = getattr(file, 'name', '')
    if filename:
        ext = os.path.splitext(filename.lower())[1]
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValidationError(f'Extensão de arquivo não permitida: {ext}. Extensões permitidas: {", ".join(ALLOWED_IMAGE_EXTENSIONS)}')
    
    # Sanitiza nome do arquivo
    if filename:
        sanitized = sanitize_filename(filename)
        if sanitized != filename:
            file.name = sanitized
            logger.info(f"Nome de arquivo sanitizado: {filename} -> {sanitized}")

    return file


def validate_video_file(file, max_size=MAX_VIDEO_SIZE):
    """
    Valida arquivo de vídeo.
    
    Args:
        file: Arquivo Django UploadedFile
        max_size: Tamanho máximo em bytes (padrão: 100MB)
        
    Raises:
        ValidationError: Se o arquivo não for válido
    """
    if not file:
        raise ValidationError('Nenhum arquivo fornecido.')
    
    # Valida tamanho
    if hasattr(file, 'size') and file.size > max_size:
        size_mb = max_size / (1024 * 1024)
        raise ValidationError(f'O arquivo é muito grande. Tamanho máximo permitido: {size_mb}MB.')
    
    # Valida tipo MIME
    content_type = getattr(file, 'content_type', None)
    if content_type and content_type not in ALLOWED_VIDEO_TYPES:
        raise ValidationError(f'Tipo de arquivo não permitido: {content_type}. Tipos permitidos: {", ".join(ALLOWED_VIDEO_TYPES)}')
    
    # Valida extensão
    filename = getattr(file, 'name', '')
    if filename:
        ext = os.path.splitext(filename.lower())[1]
        if ext not in ALLOWED_VIDEO_EXTENSIONS:
            raise ValidationError(f'Extensão de arquivo não permitida: {ext}. Extensões permitidas: {", ".join(ALLOWED_VIDEO_EXTENSIONS)}')
    
    # Sanitiza nome do arquivo
    if filename:
        sanitized = sanitize_filename(filename)
        if sanitized != filename:
            file.name = sanitized
            logger.info(f"Nome de arquivo sanitizado: {filename} -> {sanitized}")


def validate_attachment_file(file, max_size=MAX_ATTACHMENT_SIZE):
    """
    Valida arquivo de anexo.
    
    Args:
        file: Arquivo Django UploadedFile
        max_size: Tamanho máximo em bytes (padrão: 50MB)
        
    Raises:
        ValidationError: Se o arquivo não for válido
    """
    if not file:
        raise ValidationError('Nenhum arquivo fornecido.')
    
    # Valida tamanho
    if hasattr(file, 'size') and file.size > max_size:
        size_mb = max_size / (1024 * 1024)
        raise ValidationError(f'O arquivo é muito grande. Tamanho máximo permitido: {size_mb}MB.')
    
    # Valida tipo MIME
    content_type = getattr(file, 'content_type', None)
    if content_type and content_type not in ALLOWED_ATTACHMENT_TYPES:
        raise ValidationError(f'Tipo de arquivo não permitido: {content_type}. Tipos permitidos: {", ".join(ALLOWED_ATTACHMENT_TYPES)}')
    
    # Valida extensão
    filename = getattr(file, 'name', '')
    if filename:
        ext = os.path.splitext(filename.lower())[1]
        if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
            raise ValidationError(f'Extensão de arquivo não permitida: {ext}. Extensões permitidas: {", ".join(ALLOWED_ATTACHMENT_EXTENSIONS)}')
    
    # Sanitiza nome do arquivo
    if filename:
        sanitized = sanitize_filename(filename)
        if sanitized != filename:
            file.name = sanitized
            logger.info(f"Nome de arquivo sanitizado: {filename} -> {sanitized}")
