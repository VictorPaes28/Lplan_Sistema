"""Grava snapshots diários de KPI do BI da Obra (cron ou manual)."""

from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from mapa_obras.models import Obra
from suprimentos.services.analise_obra_service import (
    AnaliseObraPeriodo,
    AnaliseObraService,
)


class Command(BaseCommand):
    help = "Registra snapshot diário de KPIs do BI para todas as obras ativas (sparklines)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--obra",
            type=int,
            help="ID da obra do mapa (mapa_obras.Obra). Se omitido, processa obras ativas.",
        )
        parser.add_argument(
            "--dias",
            type=int,
            default=1,
            help="Quantos dias retroativos processar (default: 1 = hoje).",
        )

    def handle(self, *args, **options):
        obra_id = options.get("obra")
        dias = max(1, int(options.get("dias") or 1))
        hoje = timezone.localdate()

        if obra_id:
            obras = Obra.objects.filter(pk=obra_id)
        else:
            obras = Obra.objects.filter(ativa=True)

        count = 0
        for obra in obras.iterator():
            for offset in range(dias):
                ref = hoje - timedelta(days=offset)
                periodo = AnaliseObraPeriodo(data_inicio=ref - timedelta(days=30), data_fim=ref)
                svc = AnaliseObraService(obra, periodo=periodo)
                from suprimentos.services.analise_obra_service import _resolve_project_for_obra

                project = _resolve_project_for_obra(obra)
                controle = svc._build_controle(include_progressao_completo=False)
                suprimentos = svc._build_suprimentos(include_extras=False)
                diario = svc._build_diario(project, extended=False)
                gestcontroll = svc._build_gestcontroll()
                restricoes = svc._build_restricoes()
                svc._record_kpi_snapshot(
                    project=project,
                    controle=controle,
                    restricoes=restricoes,
                    gestcontroll=gestcontroll,
                    diario=diario,
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Snapshots gravados: {count}"))
