"""
Locais da obra (Mapa de Suprimentos) ligados ao projeto do Diário.
URL canónica: /projects/<project_id>/locais/.
Vínculo obra mapa ↔ projeto: ver ``core.sync_obras`` (FK ``mapa_obras.Obra.project`` + código Sienge).
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.db.models import Count, ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.painel_sistema_access import user_can_central_obras_diario_e_mapa
from mapa_obras.models import LocalObra, Obra
from suprimentos.models import AlocacaoRecebimento, ItemMapa

from .forms_locais_obra import LocalObraPainelForm, coletar_ids_descendentes
from .models import Project
from .sync_obras import get_obra_mapa_for_project_or_404


def _require_central_projects(user):
    if not user_can_central_obras_diario_e_mapa(user):
        raise PermissionDenied('Você não tem permissão para gerir obras e locais do mapa.')


def _flat_tree_rows(obra: Obra):
    locals_qs = LocalObra.objects.filter(obra=obra).annotate(
        n_itens=Count('itens_mapa', distinct=True),
        n_aloc=Count('alocacoes', distinct=True),
    )
    by_parent: dict[int | None, list] = {}
    for loc in locals_qs:
        pid = loc.parent_id
        by_parent.setdefault(pid, []).append(loc)
    for lst in by_parent.values():
        lst.sort(key=lambda x: (x.tipo, x.nome.lower()))

    rows = []

    def walk(parent_id, depth):
        for loc in by_parent.get(parent_id, []):
            rows.append((depth, loc, loc.n_itens, loc.n_aloc))
            walk(loc.id, depth + 1)

    walk(None, 0)
    return rows


@login_required
@require_http_methods(['GET', 'POST', 'HEAD'])
def project_locais_manage_view(request, project_id: int):
    _require_central_projects(request.user)
    project = get_object_or_404(Project, pk=project_id)
    obra = get_obra_mapa_for_project_or_404(project, sync=True)

    edit_id = request.GET.get('edit')
    editing = None
    form_edit = None
    form_create = LocalObraPainelForm(obra=obra, prefix='novo')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            form_create = LocalObraPainelForm(request.POST, obra=obra, prefix='novo')
            if form_create.is_valid():
                try:
                    form_create.save()
                    messages.success(
                        request,
                        f'Local «{form_create.instance.nome}» criado na obra «{obra.nome}».',
                    )
                    return redirect('project-locais-manage', project_id=project.pk)
                except IntegrityError:
                    messages.error(
                        request,
                        'Não foi possível guardar: já existe um local com este nome nesta combinação.',
                    )
        elif action == 'update':
            pk = request.POST.get('local_id')
            try:
                loc = LocalObra.objects.get(pk=int(pk), obra=obra)
            except (ValueError, LocalObra.DoesNotExist):
                messages.error(request, 'Local não encontrado nesta obra.')
            else:
                editing = loc
                excluir = frozenset(coletar_ids_descendentes(loc.pk))
                form_edit = LocalObraPainelForm(
                    request.POST,
                    instance=loc,
                    obra=obra,
                    excluir_parent_ids=excluir,
                    prefix='edit',
                )
                if form_edit.is_valid():
                    new_parent = form_edit.cleaned_data.get('parent')
                    if new_parent and new_parent.pk in coletar_ids_descendentes(loc.pk):
                        messages.error(
                            request,
                            'Não pode escolher o próprio local nem um local que está «dentro» dele.',
                        )
                    else:
                        try:
                            form_edit.save()
                            messages.success(
                                request,
                                f'Local «{form_edit.instance.nome}» atualizado.',
                            )
                            return redirect('project-locais-manage', project_id=project.pk)
                        except IntegrityError:
                            messages.error(
                                request,
                                'Não foi possível guardar: nome duplicado neste agrupamento.',
                            )
                form_create = LocalObraPainelForm(obra=obra, prefix='novo')
        elif action == 'delete':
            pk = request.POST.get('local_id')
            try:
                loc = LocalObra.objects.get(pk=int(pk), obra=obra)
            except (ValueError, LocalObra.DoesNotExist):
                messages.error(request, 'Local não encontrado nesta obra.')
            else:
                n_aloc = AlocacaoRecebimento.objects.filter(local_aplicacao=loc).count()
                if n_aloc > 0:
                    messages.error(
                        request,
                        f'Não é possível eliminar «{loc.nome}»: existem {n_aloc} alocação(ões) '
                        'de recebimento ligadas a este local. Reatribua ou remova essas alocações primeiro.',
                    )
                else:
                    nome = loc.nome
                    n_sub = len(coletar_ids_descendentes(loc.pk)) - 1
                    try:
                        loc.delete()
                        msg = f'Local «{nome}» eliminado.'
                        if n_sub:
                            msg += f' Foram removidos também {n_sub} sublocal(is) (cascade).'
                        messages.success(request, msg)
                    except ProtectedError:
                        messages.error(
                            request,
                            f'Não é possível eliminar «{nome}»: ainda há dados protegidos '
                            'ligados a este local ou a sublocais (ex.: alocações).',
                        )
                    return redirect('project-locais-manage', project_id=project.pk)
            return redirect('project-locais-manage', project_id=project.pk)
    elif edit_id:
        try:
            editing = LocalObra.objects.get(pk=int(edit_id), obra=obra)
        except (ValueError, LocalObra.DoesNotExist):
            editing = None

    if editing and form_edit is None:
        excluir = frozenset(coletar_ids_descendentes(editing.pk))
        form_edit = LocalObraPainelForm(
            instance=editing,
            obra=obra,
            excluir_parent_ids=excluir,
            prefix='edit',
        )

    rows = _flat_tree_rows(obra)
    total_locais = LocalObra.objects.filter(obra=obra).count()
    total_itens = ItemMapa.objects.filter(obra=obra).count()

    return render(
        request,
        'core/project_locais_detail.html',
        {
            'project': project,
            'obra': obra,
            'rows': rows,
            'form_create': form_create,
            'form_edit': form_edit,
            'editing': editing,
            'total_locais': total_locais,
            'total_itens': total_itens,
        },
    )
