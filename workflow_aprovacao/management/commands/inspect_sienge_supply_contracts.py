"""
Lista valores distintos devolvidos pelo Sienge em contratos de suprimentos (GET …/supply-contracts/all).

Serve para “puxar para cá” os códigos/textos reais do vosso tenant (ex.: várias situações
de contrato, combinações de statusApproval, etc.) sem adivinhar pela internet.

Requer .env com SIENGE_API_BASE_URL e credenciais (Basic), como o sync.

Exemplo:
  python manage.py inspect_sienge_supply_contracts --max-rows 5000
  python manage.py inspect_sienge_supply_contracts --pending-validation --max-rows 5000
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Tuple

from django.core.management.base import BaseCommand

from workflow_aprovacao.services.sienge_api import SiengeCentralApiClient
from workflow_aprovacao.services.sienge_measurement_sync import (
    build_sienge_project_lookup,
    contract_external_id,
    contract_pending_sienge_authorization,
    resolve_project_for_sienge_row,
)


def _norm(v: Any) -> str:
    if v is None:
        return ''
    return str(v).strip()


class Command(BaseCommand):
    help = (
        'Agrupa contratos Sienge (supply-contracts/all) por (status, statusApproval, isAuthorized) '
        'e mostra contagens; com --pending-validation compara pendentes de autorização com obras '
        'casadas no Lplan (mesma regra do sync).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-rows',
            type=int,
            default=2000,
            help='Máximo de contratos a percorrer (paginação interna).',
        )
        parser.add_argument(
            '--pending-validation',
            action='store_true',
            help='Lista contratos com autorização pendente (isAuthorized ≠ true) e se há Project/obras.',
        )

    def handle(self, *args, **options):
        max_rows = max(1, int(options['max_rows']))
        client = SiengeCentralApiClient()
        counter: Counter[Tuple[str, str, str]] = Counter()
        sample_keys: set[str] = set()

        pending_rows: List[Dict[str, Any]] = []
        lookup = build_sienge_project_lookup() if options['pending_validation'] else None
        resolve_client = client if options['pending_validation'] else None

        for row in client.iter_supply_contracts_all(page_size=50, max_rows=max_rows):
            if isinstance(row, dict):
                if not sample_keys and row:
                    sample_keys = set(row.keys())
                st = _norm(row.get('status'))
                sa = _norm(row.get('statusApproval'))
                ia = row.get('isAuthorized')
                if isinstance(ia, bool):
                    ia_s = 'true' if ia else 'false'
                else:
                    ia_s = _norm(ia)
                counter[(st, sa, ia_s)] += 1

                if lookup is not None and contract_pending_sienge_authorization(row):
                    ext = contract_external_id(row)
                    if len(ext) > 2:
                        pending_rows.append(row)

        self.stdout.write(self.style.NOTICE(f'Percorridos até {max_rows} contratos; combinações distintas: {len(counter)}'))
        if sample_keys:
            self.stdout.write('Chaves observadas num registo (amostra): ' + ', '.join(sorted(sample_keys)))
        self.stdout.write('')
        self.stdout.write(f'{"count":>8}  {"status":<20}  {"statusApproval":<28}  isAuthorized')
        for (st, sa, ia_s), n in sorted(counter.items(), key=lambda x: (-x[1], x[0])):
            self.stdout.write(f'{n:8d}  {st[:20]:<20}  {sa[:28]:<28}  {ia_s}')

        if lookup is not None:
            with_proj: List[str] = []
            without_proj: List[str] = []
            for row in pending_rows:
                doc = _norm(row.get('documentId'))
                num = _norm(row.get('contractNumber'))
                label = f'{doc} {num}'.strip() or contract_external_id(row)
                if resolve_project_for_sienge_row(row, lookup, client=resolve_client):
                    with_proj.append(label)
                else:
                    without_proj.append(label)

            self.stdout.write('')
            self.stdout.write(self.style.NOTICE('--- Validação: autorização pendente (igual ao sync) ---'))
            self.stdout.write(
                f'Contratos com autorização pendente na amostra (até {max_rows} linhas da API): {len(pending_rows)}'
            )
            self.stdout.write(f'Com obra casada no Lplan (importam no sync): {len(with_proj)}')
            self.stdout.write(f'Sem obra casada (sync ignora): {len(without_proj)}')
            if without_proj:
                self.stdout.write(self.style.WARNING('Sem Project/obras para contractNumber:'))
                for lab in sorted(without_proj):
                    self.stdout.write(f'  - {lab}')
            if with_proj:
                self.stdout.write('Com obra casada:')
                for lab in sorted(with_proj):
                    self.stdout.write(f'  - {lab}')
            self.stdout.write(
                '\nSe no Sienge tens mais pendentes do que aqui, aumenta --max-rows '
                '(a API devolve por páginas; só contamos o que foi pedido).'
            )
            self.stdout.write(
                'Depois corre: python manage.py sync_sienge_central_measurements --only-contracts --dry-run\n'
                'e compara created/would_create com os que têm obra.'
            )
