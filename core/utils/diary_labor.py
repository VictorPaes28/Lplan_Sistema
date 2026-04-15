"""
Mão de obra no diário (DiaryLaborEntry) — mesma estrutura para tela HTML e PDF.

Várias linhas no banco para o mesmo cargo (ex.: salvamentos antigos ou duplicidade)
são consolidadas em uma linha por cargo com quantidade somada.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import ConstructionDiary


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
            item_base = {'cargo_name': e.cargo.name, 'quantity': qty}

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
