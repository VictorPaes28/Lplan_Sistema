"""
Redirecionamentos: gestão de locais do mapa em /projects/<id>/locais/ (obra mapa = project.code).
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods

from core.models import Project
from mapa_obras.models import Obra

from .painel_sistema_access import user_is_painel_sistema_admin


@login_required
@user_passes_test(user_is_painel_sistema_admin)
@require_http_methods(['GET', 'HEAD'])
def locais_obras_index(request):
    return redirect('central_project_list')


@login_required
@user_passes_test(user_is_painel_sistema_admin)
@require_http_methods(['GET', 'HEAD', 'POST'])
def locais_obra_manage(request, obra_id: int):
    obra = Obra.objects.filter(pk=obra_id).first()
    if obra is None:
        messages.error(request, 'Obra não encontrada.')
        return redirect('central_project_list')
    if obra.project_id:
        return redirect('project-locais-manage', project_id=obra.project_id)
    project = Project.objects.filter(code=obra.codigo_sienge).first()
    if project is None:
        messages.warning(
            request,
            f'Existe obra no Mapa («{obra.nome}», código {obra.codigo_sienge}) sem projeto correspondente '
            'no Diário. Crie uma obra em /projects/ com o mesmo código para gerir os locais aqui.',
        )
        return redirect('central_project_list')
    return redirect('project-locais-manage', project_id=project.pk)
