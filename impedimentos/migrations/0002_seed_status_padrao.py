from django.db import migrations


STATUS_PADRAO = [
    {"nome": "Não iniciado", "cor": "#6B7280", "ordem": 1},
    {"nome": "Em progresso", "cor": "#3B82F6", "ordem": 2},
    {"nome": "Finalizado", "cor": "#16A34A", "ordem": 3},
]


def seed_status_padrao(apps, schema_editor):
    Obra = apps.get_model("gestao_aprovacao", "Obra")
    StatusImpedimento = apps.get_model("impedimentos", "StatusImpedimento")

    for obra in Obra.objects.all().iterator():
        for idx, payload in enumerate(STATUS_PADRAO):
            StatusImpedimento.objects.update_or_create(
                obra=obra,
                nome=payload["nome"],
                defaults={
                    "cor": payload["cor"],
                    "ordem": payload["ordem"],
                    "is_default": idx == 0,
                },
            )


class Migration(migrations.Migration):
    dependencies = [
        ("impedimentos", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_status_padrao, migrations.RunPython.noop),
    ]
