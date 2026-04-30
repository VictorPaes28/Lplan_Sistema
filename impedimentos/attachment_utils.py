"""Validação de anexos (ficheiros) nas restrições."""
import os

from .models import ArquivoImpedimento

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_ARQUIVOS = 5

ALLOWED_ARQUIVO_EXT = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".txt",
    ".zip",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}


def _ext_lower(filename):
    if not filename or "." not in filename:
        return ""
    return os.path.splitext(filename)[1].lower()


def validate_upload_file(f, allowed_ext, label):
    """Levanta ValueError com mensagem em português se inválido."""
    if not f:
        return
    name = getattr(f, "name", "") or ""
    ext = _ext_lower(name)
    if ext not in allowed_ext:
        raise ValueError(
            f"{label}: extensão não permitida ({ext or 'sem extensão'}). "
            f"Permitidas: {', '.join(sorted(allowed_ext))}."
        )
    size = getattr(f, "size", None)
    if size is not None and size > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"{label}: ficheiro excede o limite de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )


def validate_arquivo_upload(f):
    validate_upload_file(f, ALLOWED_ARQUIVO_EXT, "Arquivo")


def apply_impedimento_attachments_from_request(request, impedimento):
    """
    Remove anexos marcados no POST e cria novos a partir de request.FILES.
    Deve correr dentro de transaction.atomic após impedimento.save().
    Levanta ValueError com mensagem para o utilizador.
    """
    remover_arq_ids = request.POST.getlist("remover_arquivo")
    for rid in remover_arq_ids:
        try:
            pk = int(rid)
        except (TypeError, ValueError):
            continue
        ArquivoImpedimento.objects.filter(pk=pk, impedimento=impedimento).delete()

    current_arq = ArquivoImpedimento.objects.filter(impedimento=impedimento).count()

    novos_arquivos = [
        f
        for f in request.FILES.getlist("arquivos_novos")
        if f and getattr(f, "name", "")
    ]
    if len(novos_arquivos) > MAX_ARQUIVOS:
        raise ValueError(f"Pode anexar no máximo {MAX_ARQUIVOS} arquivos de cada vez.")
    if current_arq + len(novos_arquivos) > MAX_ARQUIVOS:
        raise ValueError(
            f"No máximo {MAX_ARQUIVOS} arquivos por restrição (já existem {current_arq})."
        )
    for f in novos_arquivos:
        validate_arquivo_upload(f)
        nome = os.path.basename(getattr(f, "name", "") or "")
        ArquivoImpedimento.objects.create(
            impedimento=impedimento,
            arquivo=f,
            nome_original=nome[:255],
        )
