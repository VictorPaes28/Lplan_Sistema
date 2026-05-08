from django.db import migrations, models


def backfill_modo_editor(apps, schema_editor):
    AmbienteOperacional = apps.get_model("painel_operacional", "AmbienteOperacional")
    AmbienteOperacional.objects.filter(tipo="mapa_controle").update(modo_editor="mapa_dedicado")
    AmbienteOperacional.objects.exclude(tipo="mapa_controle").update(modo_editor="quadro")


def revert_backfill_modo_editor(apps, schema_editor):
    AmbienteOperacional = apps.get_model("painel_operacional", "AmbienteOperacional")
    AmbienteOperacional.objects.update(modo_editor="quadro")


class Migration(migrations.Migration):

    dependencies = [
        ("painel_operacional", "0003_ambienteelemento_ambientecelula_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="ambienteoperacional",
            name="modo_editor",
            field=models.CharField(
                choices=[("mapa_dedicado", "Mapa dedicado"), ("quadro", "Quadro")],
                default="quadro",
                max_length=20,
            ),
        ),
        migrations.RunPython(backfill_modo_editor, revert_backfill_modo_editor),
    ]

