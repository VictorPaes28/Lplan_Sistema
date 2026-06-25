from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("mapa_obras", "0001_initial"),
        ("suprimentos", "0017_itemmapaservicostatusref"),
    ]

    operations = [
        migrations.CreateModel(
            name="BiObraKpiSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("data", models.DateField(db_index=True)),
                (
                    "avanco_fisico_pct",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True),
                ),
                ("restricoes_abertas", models.PositiveIntegerField(default=0)),
                ("pendentes_gestcontroll", models.PositiveIntegerField(default=0)),
                ("rdos_pendentes", models.PositiveIntegerField(default=0)),
                ("ocorrencias_dia", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "obra",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bi_kpi_snapshots",
                        to="mapa_obras.obra",
                    ),
                ),
            ],
            options={
                "verbose_name": "Snapshot KPI BI da Obra",
                "verbose_name_plural": "Snapshots KPI BI da Obra",
                "ordering": ["-data"],
            },
        ),
        migrations.AddConstraint(
            model_name="biobrakpisnapshot",
            constraint=models.UniqueConstraint(
                fields=("obra", "data"), name="uniq_bi_kpi_snapshot_obra_data"
            ),
        ),
    ]
