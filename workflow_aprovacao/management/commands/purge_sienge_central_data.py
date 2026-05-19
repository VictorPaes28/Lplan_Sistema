"""
Remove processos e pendências da Central criados pela ingestão Sienge (ambiente local / limpeza).

Não remove processos do GestControll (``external_entity_type=gestao_workorder`` ou vínculo
``GestaoCentralDispatch``).

Exemplos:
  python manage.py purge_sienge_central_data --dry-run
  python manage.py purge_sienge_central_data
  python manage.py purge_sienge_central_data --include-backlog
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from workflow_aprovacao.models import (
    ApprovalConfigBacklog,
    ApprovalIntegrationOutbox,
    ApprovalProcess,
    SiengeCentralSyncState,
)

SIENGE_ENTITY_TYPES = (
    'sienge_supply_contract',
    'sienge_supply_contract_measurement',
)


def sienge_processes_qs():
    return ApprovalProcess.objects.filter(
        Q(external_system='sienge')
        | Q(external_entity_type__in=SIENGE_ENTITY_TYPES)
    ).exclude(gestao_dispatch__isnull=False)


def sienge_backlog_qs():
    return ApprovalConfigBacklog.objects.filter(external_system='sienge')


class Command(BaseCommand):
    help = 'Apaga processos/pendências da Central originados do Sienge (mantém GestControll).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas mostra quantos registos seriam apagados.',
        )
        parser.add_argument(
            '--include-backlog',
            action='store_true',
            default=True,
            help='Apaga também pendências de configuração Sienge (default: sim).',
        )
        parser.add_argument(
            '--reset-sync-state',
            action='store_true',
            help='Limpa estatísticas em SiengeCentralSyncState.',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        proc_qs = sienge_processes_qs()
        proc_count = proc_qs.count()
        backlog_count = sienge_backlog_qs().count() if options['include_backlog'] else 0

        outbox_count = ApprovalIntegrationOutbox.objects.filter(
            process_id__in=proc_qs.values_list('pk', flat=True)
        ).count()

        self.stdout.write(
            self.style.MIGRATE_HEADING('\n=== Limpeza Sienge na Central ===\n')
        )
        self.stdout.write(f'  Processos Sienge a remover: {proc_count}')
        self.stdout.write(f'  Itens outbox ligados: {outbox_count}')
        if options['include_backlog']:
            self.stdout.write(f'  Pendências de configuração (backlog) Sienge: {backlog_count}')

        gestao_kept = ApprovalProcess.objects.filter(
            Q(external_entity_type='gestao_workorder') | Q(gestao_dispatch__isnull=False)
        ).count()
        self.stdout.write(f'  Processos GestControll (mantidos): {gestao_kept}')

        if dry:
            self.stdout.write(self.style.WARNING('\nDry-run: nada foi apagado.\n'))
            return

        if proc_count == 0 and backlog_count == 0:
            self.stdout.write(self.style.SUCCESS('\nNada do Sienge para apagar.\n'))
            return

        with transaction.atomic():
            deleted_proc, _ = proc_qs.delete()
            deleted_backlog = 0
            if options['include_backlog']:
                deleted_backlog, _ = sienge_backlog_qs().delete()
            if options['reset_sync_state']:
                state = SiengeCentralSyncState.objects.filter(pk=1).first()
                if state:
                    state.last_stats = {}
                    state.last_error = ''
                    state.save(update_fields=['last_stats', 'last_error'])

        self.stdout.write(
            self.style.SUCCESS(
                f'\nConcluído: {deleted_proc} processo(s) Sienge removido(s); '
                f'{deleted_backlog} pendência(s) de backlog removida(s).\n'
            )
        )
