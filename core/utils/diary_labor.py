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
    from core.models import ConstructionDiary, Labor


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
    return [{'company': c, 'items': items} for c, items in by_company.items()]


def merge_labor_entries_m2m_fallback_for_html(
    labor_entries_by_category: Optional[Dict[str, Any]],
    diary: 'ConstructionDiary',
) -> Optional[Dict[str, Any]]:
    """
    Quando há ``DiaryLaborEntry`` o PDF ainda preenche colunas vazias com o M2M
    ``resources_labor``; o template HTML só mostrava esse fallback se não existisse
    nenhuma linha em ``DiaryLaborEntry``. Replica o preenchimento por categoria vazia
    para alinhar detalhe ao PDF e aos totais.
    """
    if labor_entries_by_category is None:
        return None

    out: Dict[str, Any] = {
        'indireta': list(labor_entries_by_category.get('indireta') or []),
        'direta': list(labor_entries_by_category.get('direta') or []),
        'terceirizada': [
            {
                'company': b.get('company'),
                'items': [dict(i) for i in (b.get('items') or [])],
            }
            for b in (labor_entries_by_category.get('terceirizada') or [])
        ],
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

            if slug == 'terceirizada':
                company = e.company or '(Sem empresa)'
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
            out_terceirizada.append({
                'company': company,
                'items': list(by_cargo.values()),
            })

        return {
            'indireta': list(indireta.values()),
            'direta': list(direta.values()),
            'terceirizada': out_terceirizada,
        }
    except Exception:
        return None
