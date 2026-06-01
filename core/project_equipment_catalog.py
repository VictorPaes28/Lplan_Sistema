"""
Catálogo de equipamentos configurável por obra (RDO).
Copia o template global na primeira utilização e permite personalização por projeto.
"""
from __future__ import annotations

from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.utils.text import slugify

from .models import (
    EquipmentCategory,
    Project,
    ProjectEquipmentCategory,
    ProjectEquipmentItem,
    StandardEquipment,
)


def project_has_equipment_catalog(project: Project) -> bool:
    return ProjectEquipmentCategory.objects.filter(project=project).exists()


@transaction.atomic
def ensure_project_equipment_catalog(project: Project) -> None:
    """Cria cópia do catálogo global na obra, se ainda não existir."""
    if project_has_equipment_catalog(project):
        return

    global_categories = (
        EquipmentCategory.objects.prefetch_related('items')
        .order_by('order', 'pk')
    )
    for gcat in global_categories:
        pcat = ProjectEquipmentCategory.objects.create(
            project=project,
            slug=gcat.slug,
            name=gcat.name,
            order=gcat.order,
            is_active=True,
        )
        for gitem in gcat.items.all().order_by('order', 'name'):
            ProjectEquipmentItem.objects.create(
                project=project,
                category=pcat,
                name=gitem.name,
                order=gitem.order,
                is_active=True,
                source_standard_equipment=gitem,
            )


def get_equipment_categories_for_diary(project: Project):
    """Categorias e itens ativos para o formulário RDO."""
    ensure_project_equipment_catalog(project)
    active_items = ProjectEquipmentItem.objects.filter(
        project=project,
        is_active=True,
    ).order_by('order', 'name')
    return (
        ProjectEquipmentCategory.objects.filter(project=project, is_active=True)
        .prefetch_related(Prefetch('items', queryset=active_items))
        .order_by('order', 'pk')
    )


def get_equipment_categories_for_manage(project: Project):
    """Todas as categorias/itens da obra (inclui inativos) para a tela de gestão."""
    ensure_project_equipment_catalog(project)
    all_items = ProjectEquipmentItem.objects.filter(project=project).order_by(
        'category__order', 'order', 'name'
    )
    return (
        ProjectEquipmentCategory.objects.filter(project=project)
        .prefetch_related(Prefetch('items', queryset=all_items))
        .order_by('order', 'pk')
    )


def find_project_item_for_name(project: Project, name: str) -> ProjectEquipmentItem | None:
    """Busca item ativo do catálogo da obra por nome (case-insensitive)."""
    if not name or not str(name).strip():
        return None
    ensure_project_equipment_catalog(project)
    normalized = str(name).strip()
    return (
        ProjectEquipmentItem.objects.filter(
            project=project,
            is_active=True,
            name__iexact=normalized,
        )
        .select_related('source_standard_equipment')
        .order_by('pk')
        .first()
    )


def enrich_existing_diary_equipment(project: Project, items: list[dict]) -> list[dict]:
    """Acrescenta project_equipment_item_id (e standard legado) ao repopular o RDO."""
    if not project or not items:
        return items
    ensure_project_equipment_catalog(project)
    by_name = {}
    for proj_item in ProjectEquipmentItem.objects.filter(
        project=project,
        is_active=True,
    ).select_related('source_standard_equipment'):
        key = str(proj_item.name or '').strip().casefold()
        if key and key not in by_name:
            by_name[key] = proj_item
    for item in items:
        name = (item.get('name') or '').strip()
        if not name:
            continue
        proj_item = by_name.get(name.casefold())
        if proj_item:
            item['project_equipment_item_id'] = proj_item.pk
            if proj_item.source_standard_equipment_id:
                item['standard_equipment_id'] = proj_item.source_standard_equipment_id
    return items


def _unique_category_slug(project: Project, base: str) -> str:
    slug_base = slugify(base)[:40] or 'categoria'
    slug = slug_base
    n = 2
    while ProjectEquipmentCategory.objects.filter(project=project, slug=slug).exists():
        suffix = f'-{n}'
        slug = f'{slug_base[: max(1, 40 - len(suffix))]}{suffix}'
        n += 1
    return slug


def add_or_reactivate_project_equipment_item(
    project: Project,
    category_slug: str,
    name: str,
) -> tuple[ProjectEquipmentItem, bool]:
    """
    Cria item no catálogo da obra ou reativa existente (mesmo nome na categoria).
    Retorna (item, created).
    """
    from django.db import IntegrityError

    ensure_project_equipment_catalog(project)
    slug = (category_slug or '').strip()
    label = (name or '').strip()
    if not slug:
        raise ValueError('Selecione a categoria.')
    if not label:
        raise ValueError('Informe o nome do equipamento.')

    category = (
        ProjectEquipmentCategory.objects.filter(project=project, slug=slug)
        .order_by('-is_active', 'pk')
        .first()
    )
    if not category:
        raise ValueError('Categoria não encontrada nesta obra.')

    existing = ProjectEquipmentItem.objects.filter(
        category=category,
        name__iexact=label,
    ).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.save(update_fields=['is_active'])
        return existing, False

    last = (
        ProjectEquipmentItem.objects.filter(category=category)
        .order_by('-order')
        .values_list('order', flat=True)
        .first()
    )
    order = (last or 0) + 1
    try:
        item = ProjectEquipmentItem.objects.create(
            project=project,
            category=category,
            name=label,
            order=order,
            is_active=True,
        )
        return item, True
    except IntegrityError:
        item = ProjectEquipmentItem.objects.filter(
            category=category,
            name__iexact=label,
        ).first()
        if item:
            return item, False
        raise


def create_project_equipment_category(project: Project, name: str, order: int | None = None) -> ProjectEquipmentCategory:
    ensure_project_equipment_catalog(project)
    if order is None:
        last = (
            ProjectEquipmentCategory.objects.filter(project=project)
            .order_by('-order')
            .values_list('order', flat=True)
            .first()
        )
        order = (last or 0) + 1
    return ProjectEquipmentCategory.objects.create(
        project=project,
        slug=_unique_category_slug(project, name),
        name=name.strip(),
        order=order,
        is_active=True,
    )


def diary_equipment_catalog_url_context(project: Project | None) -> dict:
    """URLs do catálogo de equipamentos para o formulário do RDO."""
    if not project or not getattr(project, 'pk', None):
        return {}
    from django.urls import NoReverseMatch, reverse

    try:
        return {
            'equipment_catalog_json_url': reverse(
                'project-equipment-catalog-json',
                kwargs={'project_id': project.pk},
            ),
            'equipment_catalog_manage_embedded_url': (
                reverse('project-equipment-catalog-manage', kwargs={'project_id': project.pk})
                + '?embedded=1'
            ),
        }
    except NoReverseMatch:
        return {}
