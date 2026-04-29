"""
Lista automaticamente, via API Sienge, contratos (e opcionalmente medições) com autorização pendente.

Critério igual ao sync: ``isAuthorized`` nao e ``True`` (contratos); ``authorized`` nao e ``True`` (medições).

Percorre todas as páginas até a API acabar (limite de segurança configurável).

Exemplos:
  python manage.py list_sienge_pending_authorization
  python manage.py list_sienge_pending_authorization --json
  python manage.py list_sienge_pending_authorization --include-measurements
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from django.core.management.base import BaseCommand

from workflow_aprovacao.services.sienge_api import SiengeCentralApiClient
from workflow_aprovacao.services.sienge_measurement_sync import (
    build_sienge_project_lookup,
    contract_external_id,
    contract_pending_sienge_authorization,
    measurement_external_id,
    measurement_pending_sienge_authorization,
    resolve_project_for_sienge_row,
)


def _s(v: Any) -> str:
    if v is None:
        return ''
    return str(v).strip()


class Command(BaseCommand):
    help = (
        'Consulta a API Sienge e lista contratos de suprimentos pendentes de autorização '
        '(sem precisar de indicar números manualmente). Opcionalmente medições pendentes.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--hard-cap',
            type=int,
            default=200_000,
            help='Máximo de linhas a ler por recurso (proteção; default 200000).',
        )
        parser.add_argument(
            '--include-measurements',
            action='store_true',
            help='Também lista medições de contrato com authorized != true.',
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Saída em JSON (array de objetos).',
        )

    def handle(self, *args, **options):
        hard_cap = max(1, int(options['hard_cap']))
        as_json = options['json']
        client = SiengeCentralApiClient()
        lookup = build_sienge_project_lookup()

        contracts_out: List[Dict[str, Any]] = []
        for row in client.iter_supply_contracts_full_scan(page_size=50, max_total_rows=hard_cap):
            if not isinstance(row, dict):
                continue
            if not contract_pending_sienge_authorization(row):
                continue
            ext = contract_external_id(row)
            if len(ext) <= 2:
                continue
            proj = resolve_project_for_sienge_row(row, lookup, client=client)
            contracts_out.append(
                {
                    'tipo': 'contrato',
                    'external_id': ext,
                    'documentId': _s(row.get('documentId')),
                    'contractNumber': _s(row.get('contractNumber')),
                    'status': row.get('status'),
                    'statusApproval': row.get('statusApproval'),
                    'isAuthorized': row.get('isAuthorized'),
                    'lplan_tem_obra': proj is not None,
                    'lplan_obra_code': getattr(proj, 'code', None) if proj else None,
                }
            )

        measurements_out: List[Dict[str, Any]] = []
        if options['include_measurements']:
            for row in client.iter_supply_contract_measurements_full_scan(
                page_size=50, max_total_rows=hard_cap
            ):
                if not isinstance(row, dict):
                    continue
                if not measurement_pending_sienge_authorization(row):
                    continue
                ext = measurement_external_id(row)
                if len(ext) <= 2:
                    continue
                proj = resolve_project_for_sienge_row(row, lookup, client=client)
                measurements_out.append(
                    {
                        'tipo': 'medicao',
                        'external_id': ext,
                        'documentId': _s(row.get('documentId')),
                        'contractNumber': _s(row.get('contractNumber')),
                        'buildingId': row.get('buildingId'),
                        'measurementNumber': row.get('measurementNumber'),
                        'statusApproval': row.get('statusApproval'),
                        'authorized': row.get('authorized'),
                        'lplan_tem_obra': proj is not None,
                        'lplan_obra_code': getattr(proj, 'code', None) if proj else None,
                    }
                )

        if as_json:
            payload = {'contratos_pendentes': contracts_out, 'total_contratos': len(contracts_out)}
            if options['include_measurements']:
                payload['medicoes_pendentes'] = measurements_out
                payload['total_medicoes'] = len(measurements_out)
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        self.stdout.write(
            self.style.NOTICE(
                f'Contratos de suprimentos com autorização pendente (API, até {hard_cap} linhas): {len(contracts_out)}'
            )
        )
        for item in contracts_out:
            doc = item['documentId']
            num = item['contractNumber']
            ob = 'obra OK' if item['lplan_tem_obra'] else 'SEM obra no Lplan'
            code = item['lplan_obra_code'] or ''
            self.stdout.write(
                f"  {doc} {num}  |  status={item['status']!r}  statusApproval={item['statusApproval']!r}  "
                f"isAuthorized={item['isAuthorized']!r}  |  {ob} {code}"
            )

        if options['include_measurements']:
            self.stdout.write('')
            self.stdout.write(
                self.style.NOTICE(
                    f'Medições com autorização pendente: {len(measurements_out)}'
                )
            )
            for item in measurements_out:
                ob = 'obra OK' if item['lplan_tem_obra'] else 'SEM obra no Lplan'
                code = item['lplan_obra_code'] or ''
                self.stdout.write(
                    f"  {item['documentId']} {item['contractNumber']}  "
                    f"obraSienge={item['buildingId']} med={item['measurementNumber']}  "
                    f"authorized={item['authorized']!r}  |  {ob} {code}"
                )
