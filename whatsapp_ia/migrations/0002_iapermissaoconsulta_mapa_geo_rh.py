from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_ia', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='iapermissaoconsulta',
            name='pode_consultar_mapa_geo',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='iapermissaoconsulta',
            name='pode_consultar_rh',
            field=models.BooleanField(default=False),
        ),
    ]
