"""
Mão de obra no diário (DiaryLaborEntry) — mesma estrutura para tela HTML e PDF.

Várias linhas no banco para o mesmo cargo (ex.: salvamentos antigos ou duplicidade)
são consolidadas em uma linha por cargo com quantidade somada.

Quantidades são sempre ``int`` somados a partir de ``DiaryLaborEntry.quantity``;
não há arredondamento nem valores inventados. Categorias com slug fora de
``direta`` / ``indireta`` / ``terceirizada`` são ignoradas e registadas em log.
"""
from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Any, Dict, List, Optional, TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.models import ConstructionDiary, Labor, Project


def effective_labor_category_slug(labor_item: Dict[str, Any]) -> str:
    """Slug da categoria efetiva: empresa preenchida implica terceirizada."""
    company = (labor_item.get('company') or '').strip()
    if company:
        return 'terceirizada'
    return (labor_item.get('category_slug') or labor_item.get('categorySlug') or '').strip()


def _labor_cargo_in_global_category(cargo_name: str, category_slug: str, *, order: int = 0) -> int:
    from core.models import LaborCargo, LaborCategory

    gcat = LaborCategory.objects.filter(slug=category_slug).first()
    if gcat is None or not cargo_name:
        return None  # type: ignore[return-value]
    existing = LaborCargo.objects.filter(category=gcat, name__iexact=cargo_name).only('id').first()
    if existing:
        return existing.id
    return LaborCargo.objects.create(category=gcat, name=cargo_name, order=order).id


def resolve_labor_cargo_from_payload_item(
    labor_item: Dict[str, Any],
    project: Optional['Project'] = None,
) -> tuple[Optional[int], str]:
    """
    Resolve ``LaborCargo.pk`` a partir do payload do RDO, respeitando categoria
    (equipe vs terceirizada). Entradas com ``company`` nunca devem usar cargo de
    ``direta``/``indireta``.
    """
    from core.models import LaborCargo, LaborCategory, ProjectLaborItem

    cargo_name = (labor_item.get('cargo_name') or labor_item.get('cargoName') or '').strip()
    effective_slug = effective_labor_category_slug(labor_item)
    category_slug = (labor_item.get('category_slug') or labor_item.get('categorySlug') or '').strip()

    project_labor_item_id = labor_item.get('project_labor_item_id')
    if project_labor_item_id:
        try:
            pli_qs = ProjectLaborItem.objects.select_related(
                'source_labor_cargo',
                'source_labor_cargo__category',
                'category',
            ).filter(pk=int(project_labor_item_id))
            if project:
                pli_qs = pli_qs.filter(project=project)
            pli = pli_qs.get()
            cargo_name = pli.name or cargo_name
            pli_slug = pli.category.slug if pli.category_id else ''
            if effective_slug and pli_slug and pli_slug != effective_slug and project:
                alt = (
                    ProjectLaborItem.objects.filter(
                        project=project,
                        category__slug=effective_slug,
                        name__iexact=pli.name,
                        is_active=True,
                    )
                    .select_related('source_labor_cargo', 'source_labor_cargo__category', 'category')
                    .order_by('pk')
                    .first()
                )
                if alt:
                    pli = alt
                    pli_slug = pli.category.slug if pli.category_id else effective_slug
            target_slug = effective_slug or pli_slug
            if pli.source_labor_cargo_id:
                src = pli.source_labor_cargo
                src_slug = src.category.slug if src.category_id else ''
                if not target_slug or src_slug == target_slug:
                    return pli.source_labor_cargo_id, cargo_name
            if target_slug:
                cid = _labor_cargo_in_global_category(cargo_name, target_slug, order=pli.order)
                if cid:
                    return cid, cargo_name
        except (ProjectLaborItem.DoesNotExist, ValueError, TypeError):
            pass

    cargo_id = labor_item.get('cargo_id') or labor_item.get('cargoId')
    if cargo_id:
        try:
            cid = int(cargo_id)
            cargo = LaborCargo.objects.select_related('category').filter(pk=cid).first()
            if cargo:
                cargo_name = cargo_name or cargo.name
                cargo_slug = cargo.category.slug if cargo.category_id else ''
                if effective_slug and cargo_slug and cargo_slug != effective_slug:
                    resolved = _labor_cargo_in_global_category(cargo_name, effective_slug)
                    if resolved:
                        return resolved, cargo_name
                return cid, cargo_name
        except (ValueError, TypeError):
            pass

    if project and cargo_name:
        from core.project_labor_catalog import ensure_project_labor_catalog

        ensure_project_labor_catalog(project)
        pli = None
        if effective_slug:
            pli = (
                ProjectLaborItem.objects.filter(
                    project=project,
                    category__slug=effective_slug,
                    name__iexact=cargo_name,
                    is_active=True,
                )
                .select_related('source_labor_cargo', 'source_labor_cargo__category', 'category')
                .order_by('pk')
                .first()
            )
        if pli:
            return resolve_labor_cargo_from_payload_item(
                {
                    'project_labor_item_id': pli.pk,
                    'cargo_name': cargo_name,
                    'category_slug': effective_slug or category_slug,
                    'company': labor_item.get('company') or '',
                },
                project,
            )

    target_slug = effective_slug or category_slug
    if not target_slug or not cargo_name:
        return None, cargo_name

    gcat = LaborCategory.objects.filter(slug=target_slug).first()
    if gcat is None:
        return None, cargo_name

    existing_cargo = LaborCargo.objects.filter(
        category=gcat,
        name__iexact=cargo_name,
    ).only('id').first()
    if existing_cargo:
        return existing_cargo.id, cargo_name
    return LaborCargo.objects.create(
        category=gcat,
        name=cargo_name,
        order=0,
    ).id, cargo_name


def fix_misclassified_terceirizada_labor_entries(*, dry_run: bool = False) -> int:
    """
    Corrige ``DiaryLaborEntry`` com empresa preenchida mas cargo fora da categoria
    terceirizada (dados salvos antes da separação equipe/terceirizada).
    """
    from core.models import DiaryLaborEntry

    qs = (
        DiaryLaborEntry.objects.filter(company__gt='')
        .exclude(cargo__category__slug='terceirizada')
        .select_related('cargo', 'cargo__category')
    )
    fixed = 0
    for entry in qs.iterator():
        cargo_name = entry.cargo.name
        new_cargo_id = _labor_cargo_in_global_category(cargo_name, 'terceirizada')
        if not new_cargo_id or new_cargo_id == entry.cargo_id:
            continue
        if not dry_run:
            entry.cargo_id = new_cargo_id
            entry.save(update_fields=['cargo_id'])
        fixed += 1
    return fixed


def _m2m_labor_display_name(labor: 'Labor') -> str:
    """Alinha ao PDF (_lab_name): nome do cadastro ou função exibível."""
    n = getattr(labor, 'name', None)
    if n:
        return n
    if hasattr(labor, 'get_role_display') and callable(getattr(labor, 'get_role_display')):
        return labor.get_role_display() or '—'
    return '—'


def _m2m_aggregate_by_composite_key(diary: 'ConstructionDiary', labor_type_code: str) -> 'OrderedDict[str, Dict[str, Any]]':
    """
    Mesma regra que ``pdf_generator.generate_diary_pdf`` (chave name+role+company).
    """
    bucket: 'OrderedDict[str, Dict[str, Any]]' = OrderedDict()
    for wl in diary.work_logs.all():
        for labor in wl.resources_labor.all():
            if labor.labor_type != labor_type_code:
                continue
            key = f"{labor.name or ''}_{labor.role or ''}_{labor.company or ''}"
            if key not in bucket:
                bucket[key] = {'labor': labor, 'count': 0}
            bucket[key]['count'] += 1
    return bucket


def _rows_from_m2m_bucket(bucket: 'OrderedDict[str, Dict[str, Any]]') -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in bucket.values():
        lab = item['labor']
        rows.append({
            'cargo_name': _m2m_labor_display_name(lab),
            'quantity': int(item['count']),
        })
    return rows


def _terceirizada_blocks_from_m2m(diary: 'ConstructionDiary') -> List[Dict[str, Any]]:
    """Agrupa efetivo T do M2M por empresa (layout do detalhe HTML)."""
    bucket = _m2m_aggregate_by_composite_key(diary, 'T')
    if not bucket:
        return []
    by_company: 'OrderedDict[str, List[Dict[str, Any]]]' = OrderedDict()
    for item in bucket.values():
        lab = item['labor']
        company = (getattr(lab, 'company', None) or '').strip() or '(Sem empresa)'
        row = {
            'cargo_name': _m2m_labor_display_name(lab),
            'quantity': int(item['count']),
        }
        if company not in by_company:
            by_company[company] = []
        by_company[company].append(row)
    return [
        {'company': c, 'items': items, 'company_total': sum(int(i['quantity']) for i in items)}
        for c, items in by_company.items()
    ]


def merge_labor_entries_m2m_fallback_for_html(
    labor_entries_by_category: Optional[Dict[str, Any]],
    diary: 'ConstructionDiary',
) -> Optional[Dict[str, Any]]:
    """
    Quando não há ``DiaryLaborEntry`` (``labor_entries_by_category`` é None), trata como
    categorias vazias e preenche a partir do M2M legado — alinhado ao PDF e à cópia.
    """
    if labor_entries_by_category is None:
        labor_entries_by_category = {'indireta': [], 'direta': [], 'terceirizada': []}

    out_terceirizada_merge: List[Dict[str, Any]] = []
    for b in (labor_entries_by_category.get('terceirizada') or []):
        items = [dict(i) for i in (b.get('items') or [])]
        ct = b.get('company_total')
        if ct is None:
            ct = sum(int(i.get('quantity') or 0) for i in items)
        out_terceirizada_merge.append(
            {'company': b.get('company'), 'items': items, 'company_total': int(ct)}
        )

    out: Dict[str, Any] = {
        'indireta': list(labor_entries_by_category.get('indireta') or []),
        'direta': list(labor_entries_by_category.get('direta') or []),
        'terceirizada': out_terceirizada_merge,
    }

    if not out['indireta']:
        b = _m2m_aggregate_by_composite_key(diary, 'I')
        if b:
            out['indireta'] = _rows_from_m2m_bucket(b)

    if not out['direta']:
        b = _m2m_aggregate_by_composite_key(diary, 'D')
        if b:
            out['direta'] = _rows_from_m2m_bucket(b)

    if not out['terceirizada']:
        blocks = _terceirizada_blocks_from_m2m(diary)
        if blocks:
            out['terceirizada'] = blocks

    return out


def build_labor_entries_by_category(diary: 'ConstructionDiary') -> Optional[Dict[str, Any]]:
    """
    Agrupa DiaryLaborEntry por categoria, somando ``quantity`` por (cargo, empresa).

    Retorna None se não houver registros (a UI usa agregação legada por M2M).
    """
    try:
        from core.models import DiaryLaborEntry

        entries = (
            DiaryLaborEntry.objects.filter(diary=diary)
            .select_related('cargo', 'cargo__category')
            .order_by('cargo__category__order', 'company', 'cargo__name', 'pk')
        )
        if not entries.exists():
            return None

        indireta: 'OrderedDict[int, Dict[str, Any]]' = OrderedDict()
        direta: 'OrderedDict[int, Dict[str, Any]]' = OrderedDict()
        # company -> cargo_id -> row
        terceirizada: Dict[str, 'OrderedDict[int, Dict[str, Any]]'] = {}

        for e in entries:
            slug = e.cargo.category.slug
            cid = e.cargo_id
            qty = int(e.quantity or 0)
            company_stripped = (e.company or '').strip()

            # Empresa preenchida = terceirizada, mesmo se o FK do cargo estiver errado (legado).
            if company_stripped or slug == 'terceirizada':
                company = company_stripped or '(Sem empresa)'
                if company not in terceirizada:
                    terceirizada[company] = OrderedDict()
                bucket = terceirizada[company]
                if cid not in bucket:
                    bucket[cid] = {'cargo_name': e.cargo.name, 'quantity': 0}
                bucket[cid]['quantity'] += qty
            elif slug == 'indireta':
                if cid not in indireta:
                    indireta[cid] = {'cargo_name': e.cargo.name, 'quantity': 0}
                indireta[cid]['quantity'] += qty
            elif slug == 'direta':
                if cid not in direta:
                    direta[cid] = {'cargo_name': e.cargo.name, 'quantity': 0}
                direta[cid]['quantity'] += qty
            else:
                logger.warning(
                    'build_labor_entries_by_category: DiaryLaborEntry pk=%s ignorada; '
                    'slug de categoria desconhecido %r (esperado direta, indireta ou terceirizada).',
                    e.pk,
                    slug,
                )

        out_terceirizada: List[Dict[str, Any]] = []
        for company, by_cargo in terceirizada.items():
            cargo_rows = list(by_cargo.values())
            out_terceirizada.append({
                'company': company,
                'items': cargo_rows,
                'company_total': sum(int(row.get('quantity') or 0) for row in cargo_rows),
            })

        return {
            'indireta': list(indireta.values()),
            'direta': list(direta.values()),
            'terceirizada': out_terceirizada,
        }
    except Exception:
        return None
