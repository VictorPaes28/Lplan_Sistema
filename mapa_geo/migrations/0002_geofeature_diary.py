from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0055_constructiondiary_geolocation_data'),
        ('mapa_geo', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='geofeature',
            name='diary',
            field=models.ForeignKey(
                blank=True,
                help_text='Preenchido automaticamente para marcadores GPS de RDO',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='geo_features',
                to='core.constructiondiary',
                verbose_name='Diário de obra',
            ),
        ),
    ]
