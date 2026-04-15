"""
Agregação de equipamentos por diário — fonte única para formulário e PDF.

Regra (igual em todo o sistema):
- Se existir qualquer linha em DailyWorkLogEquipment para o diário → consolida por
  `equipment_id` usando o MAIOR `quantity` encontrado no dia (não soma entre work_logs).
  Isso evita supercontagem quando o mesmo equipamento é associado a várias atividades.
- Caso contrário (diários só com M2M antigo) → quantidade 1 por equipamento único do dia,
  ordem pela primeira ocorrência na ordem explícita dos work_logs (atividade, pk).

Parâmetro ``limit_to_work_logs`` restringe o cálculo a um subconjunto de serviços do dia
(ex.: uma atividade no histograma); a regra do maior ``quantity`` por equipamento aplica-se
dentro desse subconjunto.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import ConstructionDiary


def aggregate_equipment_for_diary(
    diary: 'ConstructionDiary',
    work_logs_ordered: Optional[List] = None,
    *,
    limit_to_work_logs: bool = False,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Retorna (rows, total_geral).

    Cada row: ``equipment_id`` (int), ``equipment`` (instância Equipment), ``quantity`` (int).

    ``limit_to_work_logs`` (filtro por atividade / subconjunto de serviços):
    quando True, ``work_logs_ordered`` deve ser a lista de ``DailyWorkLog`` desse diário
    a considerar. O *through* e o fallback M2M limitam-se a esses registros; dentro deles,
    para o mesmo ``equipment_id``, usa-se a maior ``quantity`` (igual à regra diária).
    """
    from core.models import DailyWorkLogEquipment

    order_eids: List[int] = []
    by_id: Dict[int, Dict[str, Any]] = {}

    if limit_to_work_logs:
        if not work_logs_ordered:
            return [], 0
        wl_ids = [wl.pk for wl in work_logs_ordered]
        through_qs = DailyWorkLogEquipment.objects.filter(
            work_log_id__in=wl_ids
        ).select_related('equipment').order_by('work_log_id', 'pk')
    else:
        through_qs = DailyWorkLogEquipment.objects.filter(
            work_log__diary=diary
        ).select_related('equipment').order_by('work_log_id', 'pk')

    if through_qs.exists():
        for row in through_qs:
            eq = row.equipment
            if eq is None:
                continue
            eid = row.equipment_id
            qty = int(row.quantity or 0)
            if eid not in by_id:
                by_id[eid] = {'equipment': eq, 'quantity': qty}
                order_eids.append(eid)
            else:
                # Lógica de diário: mesmo equipamento em vários serviços conta uma vez
                # com a maior quantidade usada no dia.
                if qty > by_id[eid]['quantity']:
                    by_id[eid]['quantity'] = qty
    else:
        if limit_to_work_logs:
            wls = list(work_logs_ordered or [])
        elif work_logs_ordered is not None:
            wls = list(work_logs_ordered)
        else:
            wls = list(
                diary.work_logs.select_related('activity').order_by(
                    'activity__code', 'activity__name', 'pk'
                )
            )
        for wl in wls:
            for eq in wl.resources_equipment.all():
                if eq is None:
                    continue
                eid = getattr(eq, 'pk', None)
                if eid is None:
                    continue
                if eid not in by_id:
                    by_id[eid] = {'equipment': eq, 'quantity': 1}
                    order_eids.append(eid)

    rows: List[Dict[str, Any]] = []
    for eid in order_eids:
        b = by_id[eid]
        eq = b['equipment']
        q = b['quantity']
        rows.append({
            'equipment_id': eid,
            'equipment': eq,
            'quantity': q,
        })
    total = sum(r['quantity'] for r in rows)
    return rows, total
