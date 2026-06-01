"""
Catálogo de mão de obra configurável por obra (RDO).
Copia o template global na primeira utilização e permite personalização por projeto.
"""
from __future__ import annotations

from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.utils.text import slugify

from .models import (
    LaborCategory,
    LaborCargo,
    Project,
    ProjectLaborCategory,
    ProjectLaborItem,
)


def project_has_labor_catalog(project: Project) -> bool:
    return ProjectLaborCategory.objects.filter(project=project).exists()


@transaction.atomic
def ensure_project_labor_catalog(project: Project) -> None:
    """Cria cópia do catálogo global na obra, se ainda não existir."""
    if project_has_labor_catalog(project):
        return

    global_categories = (
        LaborCategory.objects.prefetch_related('cargos')
        .order_by('order', 'pk')
    )
    for gcat in global_categories:
        pcat = ProjectLaborCategory.objects.create(
            project=project,
            slug=gcat.slug,
            name=gcat.name,
            order=gcat.order,
            is_active=True,
        )
        for gcargo in gcat.cargos.all().order_by('order', 'name'):
            ProjectLaborItem.objects.create(
                project=project,
                category=pcat,
                name=gcargo.name,
                order=gcargo.order,
                is_active=True,
                source_labor_cargo=gcargo,
            )


def get_labor_categories_for_diary(project: Project):
    """Categorias e itens ativos para o formulário RDO."""
    ensure_project_labor_catalog(project)
    active_items = ProjectLaborItem.objects.filter(
        project=project,
        is_active=True,
    ).order_by('order', 'name')
    return (
        ProjectLaborCategory.objects.filter(project=project, is_active=True)
        .prefetch_related(Prefetch('items', queryset=active_items))
        .order_by('order', 'pk')
    )


def get_labor_categories_for_manage(project: Project):
    """Todas as categorias/itens da obra (inclui inativos) para a tela de gestão."""
    ensure_project_labor_catalog(project)
    all_items = ProjectLaborItem.objects.filter(project=project).order_by(
        'category__order', 'order', 'name'
    )
    return (
        ProjectLaborCategory.objects.filter(project=project)
        .prefetch_related(Prefetch('items', queryset=all_items))
        .order_by('order', 'pk')
    )


def find_project_labor_item_for_name(project: Project, name: str) -> ProjectLaborItem | None:
    """Busca item ativo do catálogo da obra por nome (case-insensitive)."""
    if not name or not str(name).strip():
        return None
    ensure_project_labor_catalog(project)
    normalized = str(name).strip()
    return (
        ProjectLaborItem.objects.filter(
            project=project,
            is_active=True,
            name__iexact=normalized,
        )
        .select_related('source_labor_cargo', 'category')
        .order_by('pk')
        .first()
    )


def enrich_existing_diary_labor(project: Project, items: list[dict]) -> list[dict]:
    """Acrescenta project_labor_item_id (e cargo legado) ao repopular o RDO."""
    if not project or not items:
        return items
    ensure_project_labor_catalog(project)
    by_name = {}
    by_source_cargo = {}
    for proj_item in ProjectLaborItem.objects.filter(
        project=project,
        is_active=True,
    ).select_related('source_labor_cargo'):
        key = str(proj_item.name or '').strip().casefold()
        if key and key not in by_name:
            by_name[key] = proj_item
        if proj_item.source_labor_cargo_id:
            by_source_cargo[proj_item.source_labor_cargo_id] = proj_item
    for item in items:
        cargo_id = item.get('cargo_id')
        if cargo_id and cargo_id in by_source_cargo:
            item['project_labor_item_id'] = by_source_cargo[cargo_id].pk
        name = (item.get('cargo_name') or '').strip()
        if name:
            proj_item = by_name.get(name.casefold())
            if proj_item:
                item['project_labor_item_id'] = proj_item.pk
                if proj_item.source_labor_cargo_id and not item.get('cargo_id'):
                    item['cargo_id'] = proj_item.source_labor_cargo_id
    return items


def _unique_category_slug(project: Project, base: str) -> str:
    slug_base = slugify(base)[:40] or 'categoria'
    slug = slug_base
    n = 2
    while ProjectLaborCategory.objects.filter(project=project, slug=slug).exists():
        suffix = f'-{n}'
        slug = f'{slug_base[: max(1, 40 - len(suffix))]}{suffix}'
        n += 1
    return slug


def add_or_reactivate_project_labor_item(
    project: Project,
    category_slug: str,
    name: str,
) -> tuple[ProjectLaborItem, bool]:
    """
    Cria item no catálogo da obra ou reativa existente (mesmo nome na categoria).
    Retorna (item, created).
    """
    from django.db import IntegrityError

    ensure_project_labor_catalog(project)
    slug = (category_slug or '').strip()
    label = (name or '').strip()
    if not slug:
        raise ValueError('Selecione a categoria.')
    if not label:
        raise ValueError('Informe o nome do cargo.')

    category = (
        ProjectLaborCategory.objects.filter(project=project, slug=slug)
        .order_by('-is_active', 'pk')
        .first()
    )
    if not category:
        raise ValueError('Categoria não encontrada nesta obra.')

    existing = ProjectLaborItem.objects.filter(
        category=category,
        name__iexact=label,
    ).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.save(update_fields=['is_active'])
        return existing, False

    last = (
        ProjectLaborItem.objects.filter(category=category)
        .order_by('-order')
        .values_list('order', flat=True)
        .first()
    )
    order = (last or 0) + 1
    try:
        item = ProjectLaborItem.objects.create(
            project=project,
            category=category,
            name=label,
            order=order,
            is_active=True,
        )
        return item, True
    except IntegrityError:
        item = ProjectLaborItem.objects.filter(
            category=category,
            name__iexact=label,
        ).first()
        if item:
            return item, False
        raise


def create_project_labor_category(project: Project, name: str, order: int | None = None) -> ProjectLaborCategory:
    ensure_project_labor_catalog(project)
    if order is None:
        last = (
            ProjectLaborCategory.objects.filter(project=project)
            .order_by('-order')
            .values_list('order', flat=True)
            .first()
        )
        order = (last or 0) + 1
    return ProjectLaborCategory.objects.create(
        project=project,
        slug=_unique_category_slug(project, name),
        name=name.strip(),
        order=order,
        is_active=True,
    )


def diary_labor_catalog_url_context(project: Project | None) -> dict:
    """URLs do catálogo de mão de obra para o formulário do RDO."""
    if not project or not getattr(project, 'pk', None):
        return {}
    from django.urls import NoReverseMatch, reverse

    try:
        return {
            'labor_catalog_json_url': reverse(
                'project-labor-catalog-json',
                kwargs={'project_id': project.pk},
            ),
            'labor_catalog_manage_embedded_url': (
                reverse('project-labor-catalog-manage', kwargs={'project_id': project.pk})
                + '?embedded=1'
            ),
        }
    except NoReverseMatch:
        return {}
