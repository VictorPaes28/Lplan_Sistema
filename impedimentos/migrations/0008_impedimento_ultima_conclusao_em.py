from django.db import migrations, models
from django.db.models import F


def backfill_ultima_conclusao_em(apps, schema_editor):
    Impedimento = apps.get_model("impedimentos", "Impedimento")
    StatusImpedimento = apps.get_model("impedimentos", "StatusImpedimento")
    obra_ids = Impedimento.objects.values_list("obra_id", flat=True).distinct()
    for obra_id in obra_ids:
        ultimo_id = (
            StatusImpedimento.objects.filter(obra_id=obra_id)
            .order_by("-ordem")
            .values_list("pk", flat=True)
            .first()
        )
        if not ultimo_id:
            continue
        Impedimento.objects.filter(
            obra_id=obra_id,
            status_id=ultimo_id,
        ).update(ultima_conclusao_em=F("atualizado_em"))


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("impedimentos", "0007_impedimento_parent_subtarefas"),
    ]

    operations = [
        migrations.AddField(
            model_name="impedimento",
            name="ultima_conclusao_em",
            field=models.DateTimeField(
                blank=True,
                help_text="Data/hora da última vez que o impeditivo entrou no status de conclusão da obra.",
                null=True,
            ),
        ),
        migrations.RunPython(backfill_ultima_conclusao_em, noop_reverse),
    ]
