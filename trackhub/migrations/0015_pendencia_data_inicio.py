from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trackhub", "0014_pendencia_responsavel_interno"),
    ]

    operations = [
        migrations.AddField(
            model_name="pendencia",
            name="data_inicio",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="pendenciarecorrente",
            name="data_inicio_original",
            field=models.DateField(blank=True, null=True),
        ),
    ]
