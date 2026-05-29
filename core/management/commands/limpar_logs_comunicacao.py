"""
Remove registros antigos de LogDecisaoComunicacao.

Uso: python manage.py limpar_logs_comunicacao --dias=90
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.comunicacao_models import LogDecisaoComunicacao


class Command(BaseCommand):
    help = 'Remove logs de decisão de comunicação mais antigos que N dias.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=int,
            default=90,
            help='Idade mínima em dias para exclusão (padrão: 90).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas exibe quantos registros seriam removidos.',
        )

    def handle(self, *args, **options):
        dias = max(1, int(options['dias']))
        limite = timezone.now() - timedelta(days=dias)
        qs = LogDecisaoComunicacao.objects.filter(created_at__lt=limite)
        total = qs.count()
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(
                    f'[dry-run] {total} registro(s) anteriores a {limite.date()} seriam removidos.'
                )
            )
            return
        deleted, _ = qs.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f'{deleted} registro(s) de LogDecisaoComunicacao removidos (anteriores a {limite.date()}).'
            )
        )
