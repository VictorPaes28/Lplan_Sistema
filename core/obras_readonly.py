"""
Regras de obra inativa no produto.

Fonte de verdade para «ativa/inativa»: core.Project.is_active
(sincronizado com GestControll e Mapa via sync_project_to_gestao_and_mapa).

Mensagens e helpers reutilizáveis para bloquear escrita sem confundir com falta de permissão.
"""

from __future__ import annotations

UNSAFE_HTTP_METHODS = frozenset(("POST", "PUT", "PATCH", "DELETE"))

OBRA_INATIVA_CONSULTA_MSG = (
    "Esta obra está inativa. Os dados estão disponíveis apenas para consulta."
)


def project_requires_readonly(project) -> bool:
    return bool(project) and not project.is_active


def inactive_project_json_response(project):
    """403 JSON quando a obra existe mas está inativa; None se operação pode seguir."""
    if not project_requires_readonly(project):
        return None
    from django.http import JsonResponse

    return JsonResponse(
        {"ok": False, "success": False, "error": OBRA_INATIVA_CONSULTA_MSG},
        status=403,
    )


def response_for_inactive_project_write_attempt(request, project):
    """
    Bloqueio para tentativa de escrita em obra inativa.
    None = pode seguir; caso contrário HttpResponse (JSON ou redirect).
    """
    if not project_requires_readonly(project):
        return None
    accept = (request.META.get("HTTP_ACCEPT") or "").lower()
    xhr = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if xhr or "application/json" in accept:
        return inactive_project_json_response(project)
    from django.contrib import messages
    from django.shortcuts import redirect
    from django.urls import reverse

    messages.error(request, OBRA_INATIVA_CONSULTA_MSG)
    return redirect(request.META.get("HTTP_REFERER") or reverse("dashboard"))


def mapa_obra_requires_readonly(obra_mapa) -> bool:
    """
    ``mapa_obras.Obra``: ``ativa`` replica ``Project.is_active`` após sync.
    """
    return obra_mapa is not None and not getattr(obra_mapa, "ativa", True)


def inactive_mapa_obra_write_json(obra_mapa):
    """403 JSON para escritas bloqueadas no mapa de suprimentos."""
    if not mapa_obra_requires_readonly(obra_mapa):
        return None
    from django.http import JsonResponse

    return JsonResponse(
        {"ok": False, "success": False, "error": OBRA_INATIVA_CONSULTA_MSG},
        status=403,
    )


def gestao_obra_requires_readonly(obra_gestao) -> bool:
    """``gestao_aprovacao.Obra``: campo ``ativo`` espelha o Project após sync."""
    return obra_gestao is not None and not getattr(obra_gestao, "ativo", True)


def redirect_if_gestao_obra_readonly(request, workorder):
    """Redireciona ao detalhe do pedido com mensagem quando a obra Gestão está inativa."""
    if not gestao_obra_requires_readonly(workorder.obra):
        return None
    from django.contrib import messages
    from django.shortcuts import redirect

    messages.error(request, OBRA_INATIVA_CONSULTA_MSG)
    return redirect("gestao:detail_workorder", pk=workorder.pk)
