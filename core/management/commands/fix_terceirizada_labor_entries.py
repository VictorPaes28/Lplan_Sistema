"""Corrige mão de obra terceirizada salva com cargo da equipe no RDO."""

from django.core.management.base import BaseCommand

from core.utils.diary_labor import fix_misclassified_terceirizada_labor_entries


class Command(BaseCommand):
    help = (
        'Reclassifica DiaryLaborEntry com empresa preenchida mas cargo fora da '
        'categoria terceirizada (equipe vs terceirizados no RDO).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas conta quantos registros seriam corrigidos.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        fixed = fix_misclassified_terceirizada_labor_entries(dry_run=dry_run)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'{fixed} registro(s) seriam corrigidos (dry-run).')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'{fixed} registro(s) de mão de obra terceirizada corrigidos.')
            )
