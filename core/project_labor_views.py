"""
Gestão do catálogo de mão de obra do RDO por obra.
URL: /projects/<project_id>/mao-de-obra-rdo/
"""
from __future__ import annotations

import json
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms_project_labor import (
    ProjectLaborCategoryCreateForm,
    ProjectLaborCategoryForm,
    ProjectLaborItemCreateForm,
    ProjectLaborItemForm,
)
from .models import Project, ProjectLaborCategory, ProjectLaborItem
from .project_labor_catalog import (
    add_or_reactivate_project_labor_item,
    create_project_labor_category,
    ensure_project_labor_catalog,
    get_labor_categories_for_diary,
    get_labor_categories_for_manage,
)


def _is_embedded_request(request) -> bool:
    return request.GET.get('embedded') == '1' or request.POST.get('embedded') == '1'


def _require_project_labor_access(user, project: Project) -> None:
    from .frontend_views import _user_can_access_project

    if not _user_can_access_project(user, project):
        raise PermissionDenied('Você não tem acesso ao catálogo de mão de obra desta obra.')


def _manage_url(project_id: int, embedded: bool = False) -> str:
    url = reverse('project-labor-catalog-manage', kwargs={'project_id': project_id})
    return f'{url}?embedded=1' if embedded else url


def _is_ajax_request(request) -> bool:
    accept = request.headers.get('Accept') or ''
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.POST.get('ajax') == '1'
        or 'application/json' in accept
    )


def _toggle_json_response(kind: str, obj, message: str):
    return JsonResponse(
        {
            'success': True,
            'kind': kind,
            'id': obj.pk,
            'is_active': obj.is_active,
            'message': message,
        }
    )


def _manage_redirect(
    project_id: int,
    *,
    embedded: bool = False,
    updated: bool = False,
    anchor: str | None = None,
    **query,
):
    params = dict(query)
    if embedded:
        params['embedded'] = '1'
    if updated:
        params['updated'] = '1'
    url = reverse('project-labor-catalog-manage', kwargs={'project_id': project_id})
    if params:
        url = f'{url}?{urlencode(params)}'
    if anchor:
        url = f'{url}#{anchor.lstrip("#")}'
    return redirect(url)


def _catalog_context(
    project,
    *,
    embedded=False,
    catalog_updated=False,
    form_category_create,
    form_category_edit,
    form_item_create,
    form_item_edit,
    editing_category,
    editing_item,
):
    categories = get_labor_categories_for_manage(project)
    item_stats = ProjectLaborItem.objects.filter(project=project).aggregate(
        n_items=Count('id'),
        n_active=Count('id', filter=Q(is_active=True)),
    )
    return {
        'project': project,
        'categories': categories,
        'n_items': item_stats['n_items'] or 0,
        'n_active': item_stats['n_active'] or 0,
        'form_category_create': form_category_create,
        'form_category_edit': form_category_edit,
        'form_item_create': form_item_create,
        'form_item_edit': form_item_edit,
        'editing_category': editing_category,
        'editing_item': editing_item,
        'embedded': embedded,
        'manage_url': _manage_url(project.pk, embedded=embedded),
        'catalog_updated': catalog_updated,
    }


@login_required
@require_http_methods(['POST'])
def project_labor_item_add_api_view(request, project_id: int):
    """
    Adiciona cargo ao catálogo da obra a partir do formulário do RDO.
    Acesso: quem pode editar diários na obra (membro, dono, aprovador ou staff).
    """
    project = get_object_or_404(Project, pk=project_id)
    _require_project_labor_access(request.user, project)

    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        body = request.POST

    category_slug = (body.get('category_slug') or body.get('category') or '').strip()
    name = (body.get('name') or body.get('cargo_name') or '').strip()

    try:
        item, created = add_or_reactivate_project_labor_item(project, category_slug, name)
    except ValueError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)
    except IntegrityError:
        return JsonResponse(
            {'success': False, 'error': 'Não foi possível salvar: nome duplicado nesta categoria.'},
            status=400,
        )

    return JsonResponse(
        {
            'success': True,
            'created': created,
            'item': {
                'id': item.pk,
                'name': item.name,
                'category_slug': item.category.slug,
            },
        }
    )


@login_required
@require_http_methods(['GET', 'HEAD'])
def project_labor_catalog_json_view(request, project_id: int):
    """Lista ativa do catálogo (JSON) para atualizar o formulário do RDO sem recarregar a página."""
    project = get_object_or_404(Project, pk=project_id)
    _require_project_labor_access(request.user, project)
    ensure_project_labor_catalog(project)
    categories = get_labor_categories_for_diary(project)
    payload = []
    for cat in categories:
        payload.append(
            {
                'slug': cat.slug,
                'name': cat.name,
                'items': [{'id': item.pk, 'name': item.name} for item in cat.items.all()],
            }
        )
    return JsonResponse({'success': True, 'categories': payload})


@login_required
@require_http_methods(['GET', 'POST', 'HEAD'])
def project_labor_catalog_manage_view(request, project_id: int):
    project = get_object_or_404(Project, pk=project_id)
    _require_project_labor_access(request.user, project)
    ensure_project_labor_catalog(project)

    embedded = _is_embedded_request(request)
    catalog_updated = request.GET.get('updated') == '1'
    template = 'core/project_labor_catalog_embedded.html' if embedded else 'core/project_labor_catalog.html'

    edit_category_id = request.GET.get('edit_category')
    edit_item_id = request.GET.get('edit_item')
    editing_category = None
    editing_item = None
    form_category_edit = None
    form_item_edit = None
    form_category_create = ProjectLaborCategoryCreateForm(prefix='cat_novo')
    form_item_create = ProjectLaborItemCreateForm(project=project, prefix='item_novo')

    if request.method == 'POST':
        action = request.POST.get('action')
        embedded = embedded or request.POST.get('embedded') == '1'
        template = 'core/project_labor_catalog_embedded.html' if embedded else 'core/project_labor_catalog.html'

        if action == 'create_category':
            form_category_create = ProjectLaborCategoryCreateForm(request.POST, prefix='cat_novo')
            if form_category_create.is_valid():
                name = form_category_create.cleaned_data['name']
                order = form_category_create.cleaned_data.get('order')
                try:
                    create_project_labor_category(project, name, order=order)
                    messages.success(request, f'Categoria «{name}» criada.')
                    return _manage_redirect(
                        project.pk,
                        embedded=embedded,
                        updated=True,
                    )
                except IntegrityError:
                    messages.error(request, 'Não foi possível criar a categoria.')

        elif action == 'update_category':
            pk = request.POST.get('category_id')
            try:
                cat = ProjectLaborCategory.objects.get(pk=int(pk), project=project)
            except (ValueError, ProjectLaborCategory.DoesNotExist):
                messages.error(request, 'Categoria não encontrada nesta obra.')
            else:
                editing_category = cat
                form_category_edit = ProjectLaborCategoryForm(request.POST, instance=cat, prefix='cat_edit')
                if form_category_edit.is_valid():
                    try:
                        form_category_edit.save()
                        messages.success(request, f'Categoria «{cat.name}» atualizada.')
                        return _manage_redirect(
                            project.pk,
                            embedded=embedded,
                            updated=True,
                        )
                    except IntegrityError:
                        messages.error(request, 'Não foi possível salvar a categoria.')

        elif action == 'create_item':
            form_item_create = ProjectLaborItemCreateForm(request.POST, project=project, prefix='item_novo')
            if form_item_create.is_valid():
                cat = form_item_create.cleaned_data['category']
                name = form_item_create.cleaned_data['name'].strip()
                order = form_item_create.cleaned_data.get('order')
                if order is None:
                    last = (
                        ProjectLaborItem.objects.filter(category=cat)
                        .order_by('-order')
                        .values_list('order', flat=True)
                        .first()
                    )
                    order = (last or 0) + 1
                try:
                    ProjectLaborItem.objects.create(
                        project=project,
                        category=cat,
                        name=name,
                        order=order,
                        is_active=True,
                    )
                    messages.success(request, f'Cargo «{name}» adicionado à categoria «{cat.name}».')
                    return _manage_redirect(
                        project.pk,
                        embedded=embedded,
                        updated=True,
                    )
                except IntegrityError:
                    messages.error(
                        request,
                        'Já existe um cargo com este nome nesta categoria.',
                    )

        elif action == 'update_item':
            pk = request.POST.get('item_id')
            try:
                item = ProjectLaborItem.objects.select_related('category').get(
                    pk=int(pk),
                    project=project,
                )
            except (ValueError, ProjectLaborItem.DoesNotExist):
                messages.error(request, 'Cargo não encontrado nesta obra.')
            else:
                editing_item = item
                form_item_edit = ProjectLaborItemForm(
                    request.POST,
                    instance=item,
                    project=project,
                    prefix='item_edit',
                )
                if form_item_edit.is_valid():
                    try:
                        form_item_edit.save()
                        messages.success(request, f'Cargo «{item.name}» atualizado.')
                        return _manage_redirect(
                            project.pk,
                            embedded=embedded,
                            updated=True,
                        )
                    except IntegrityError:
                        messages.error(
                            request,
                            'Não foi possível salvar: nome duplicado na categoria escolhida.',
                        )

        elif action == 'toggle_item':
            pk = request.POST.get('item_id')
            try:
                item = ProjectLaborItem.objects.select_related('category').get(
                    pk=int(pk),
                    project=project,
                )
            except (ValueError, ProjectLaborItem.DoesNotExist):
                err = 'Cargo não encontrado nesta obra.'
                if _is_ajax_request(request):
                    return JsonResponse({'success': False, 'error': err}, status=404)
                messages.error(request, err)
            else:
                item.is_active = not item.is_active
                item.save(update_fields=['is_active'])
                status_label = 'visível no RDO' if item.is_active else 'oculto no RDO'
                message = f'«{item.name}» agora está {status_label}.'
                if _is_ajax_request(request):
                    return _toggle_json_response('item', item, message)
                messages.success(request, message)
                return _manage_redirect(
                    project.pk,
                    embedded=embedded,
                    updated=True,
                )

        elif action == 'toggle_category':
            pk = request.POST.get('category_id')
            try:
                cat = ProjectLaborCategory.objects.filter(pk=int(pk), project=project).first()
                if not cat:
                    raise ProjectLaborCategory.DoesNotExist
            except (ValueError, ProjectLaborCategory.DoesNotExist):
                err = 'Categoria não encontrada nesta obra.'
                if _is_ajax_request(request):
                    return JsonResponse({'success': False, 'error': err}, status=404)
                messages.error(request, err)
            else:
                cat.is_active = not cat.is_active
                cat.save(update_fields=['is_active'])
                status_label = 'visível no RDO' if cat.is_active else 'oculta no RDO'
                message = f'Categoria «{cat.name}» agora está {status_label}.'
                if _is_ajax_request(request):
                    return _toggle_json_response('category', cat, message)
                messages.success(request, message)
                return _manage_redirect(
                    project.pk,
                    embedded=embedded,
                    updated=True,
                )

    if edit_category_id and form_category_edit is None:
        try:
            editing_category = ProjectLaborCategory.objects.get(
                pk=int(edit_category_id),
                project=project,
            )
            form_category_edit = ProjectLaborCategoryForm(instance=editing_category, prefix='cat_edit')
        except (ValueError, ProjectLaborCategory.DoesNotExist):
            pass

    if edit_item_id and form_item_edit is None:
        try:
            editing_item = ProjectLaborItem.objects.get(pk=int(edit_item_id), project=project)
            form_item_edit = ProjectLaborItemForm(
                instance=editing_item,
                project=project,
                prefix='item_edit',
            )
        except (ValueError, ProjectLaborItem.DoesNotExist):
            pass

    return render(
        request,
        template,
        _catalog_context(
            project,
            embedded=embedded,
            catalog_updated=catalog_updated,
            form_category_create=form_category_create,
            form_category_edit=form_category_edit,
            form_item_create=form_item_create,
            form_item_edit=form_item_edit,
            editing_category=editing_category,
            editing_item=editing_item,
        ),
    )
