"""
View para servir arquivos de mídia em produção de forma segura.
Evita 500 quando o path tem caracteres especiais ou o arquivo não existe.
Protege contra path traversal (ex.: %2e%2e%2f).
"""
import os
from urllib.parse import unquote

from django.views.static import serve
from django.http import Http404


def serve_media_safe(request, path, document_root=None, **kwargs):
    """
    Envolve django.views.static.serve para retornar 404 em vez de 500
    quando o arquivo não existe ou path é inválido.
    Valida path após unquote para evitar path traversal.
    """
    if not document_root or not path:
        raise Http404("Recurso não encontrado")
    try:
        path_decoded = unquote(path)
    except Exception:
        raise Http404("Caminho inválido")
    path_clean = path_decoded.lstrip("/").replace("\\", "/")
    if ".." in path_clean:
        raise Http404("Caminho inválido")
    # Garante que o path resolvido está dentro de document_root
    doc_root_abs = os.path.abspath(os.path.normpath(str(document_root)))
    resolved = os.path.abspath(os.path.join(doc_root_abs, path_clean))
    if not resolved.startswith(doc_root_abs):
        raise Http404("Caminho inválido")
    try:
        return serve(request, path_decoded, document_root=document_root, **kwargs)
    except Exception:
        raise Http404("Arquivo não encontrado")
