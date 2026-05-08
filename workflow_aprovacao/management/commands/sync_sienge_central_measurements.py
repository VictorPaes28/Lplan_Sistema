"""
Sincroniza dados do Sienge para a Central de Aprovações (fase 1: receber).

Apenas contratos de suprimentos e medições de contrato (API supply-contracts).
Não inclui pedido de compra, solicitação de compra, NF de compra nem mapa de suprimentos.

Contratos: GET /v1/supply-contracts/all → categoria ``contrato``.
Medições: GET /v1/supply-contracts/measurements/all → categoria ``medicao`` (por settings).

Não altera GestControll.

Sem fluxo ativo na obra/categoria: o item entra na fila «Pendências de configuração»
(/aprovacoes/config/pendencias/) para o administrador.

Exemplos:
  python manage.py sync_sienge_central_measurements --dry-run
  python manage.py sync_sienge_central_measurements --only-measurements
  python manage.py sync_sienge_central_measurements --only-contracts
  python manage.py sync_sienge_central_measurements --category medicao
"""
from django.core.management.base import BaseCommand

from workflow_aprovacao.services.sienge_measurement_sync import (
    sync_sienge_central_inbound,
    sync_sienge_measurements_to_central,
)


class Command(BaseCommand):
    help = (
        'Lê contratos e medições no Sienge e cria processos na Central quando pendentes '
        'e quando o contractNumber Sienge casa com Project (code, contract_number, '
        'sienge_codigos_alternativos) ou obras Gestão/Mapa já ligadas ao Project.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Não grava; mostra contadores.',
        )
        parser.add_argument(
            '--any-status',
            action='store_true',
            help='Ignora filtros de pendência no Sienge (apenas testes).',
        )
        parser.add_argument(
            '--max-rows',
            type=int,
            default=None,
            help='Máximo de linhas por fonte (default: SIENGE_CENTRAL_SYNC_MAX_ROWS).',
        )
        parser.add_argument(
            '--category',
            type=str,
            default=None,
            help='Só medições: força uma categoria (contrato|medicao). Sem isto, usa SIENGE_CENTRAL_MEASUREMENT_CATEGORY_CODE.',
        )
        parser.add_argument(
            '--only-contracts',
            action='store_true',
            help='Só contratos (/supply-contracts/all).',
        )
        parser.add_argument(
            '--only-measurements',
            action='store_true',
            help='Só medições (/measurements/all).',
        )

    def handle(self, *args, **options):
        only_c = options['only_contracts']
        only_m = options['only_measurements']
        if only_c and only_m:
            self.stderr.write(self.style.ERROR('Use apenas um de --only-contracts / --only-measurements.'))
            return

        if options['category']:
            stats = sync_sienge_measurements_to_central(
                max_rows=options['max_rows'],
                category_code=options['category'],
                any_status=options['any_status'],
                dry_run=options['dry_run'],
            )
            self.stdout.write(f'measurements (categoria fixa): {stats}')
            return

        stats = sync_sienge_central_inbound(
            max_rows=options['max_rows'],
            any_status=options['any_status'],
            dry_run=options['dry_run'],
            include_contracts=not only_m,
            include_measurements=not only_c,
        )
        self.stdout.write(str(stats))
