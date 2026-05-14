from django.core.management.base import BaseCommand
from django.utils import timezone

from trackhub.recurrence_jobs import processar_todas_recorrencias


class Command(BaseCommand):
    help = (
        "Cria pendências do TrackHub a partir de séries recorrentes cuja "
        "proxima_execucao é hoje ou anterior. Agende diariamente (cron ou Celery Beat)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas mostra quantas séries estão em atraso, sem criar pendências.",
        )

    def handle(self, *args, **options):
        from trackhub.models import PendenciaRecorrente

        hoje = timezone.localdate()
        if options["dry_run"]:
            n = (
                PendenciaRecorrente.objects.filter(ativo=True)
                .exclude(regra=PendenciaRecorrente.REGRA_NONE)
                .filter(proxima_execucao__lte=hoje)
                .count()
            )
            self.stdout.write(f"Séries com execução pendente (data <= {hoje}): {n}")
            return

        total = processar_todas_recorrencias(hoje=hoje)
        self.stdout.write(self.style.SUCCESS(f"Pendências criadas por recorrência: {total}."))
