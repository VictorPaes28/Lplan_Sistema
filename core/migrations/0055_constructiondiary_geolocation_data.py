from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0054_projectfront_description_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='constructiondiary',
            name='geolocation_data',
            field=models.JSONField(
                blank=True,
                help_text='Coordenadas capturadas automaticamente ao salvar o diário (lat/lng, precisão, horário)',
                null=True,
                verbose_name='Localização GPS',
            ),
        ),
    ]
