from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0013_modulo_integrado_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersignuprequest',
            name='requested_front_ids',
            field=models.JSONField(blank=True, default=list, verbose_name='Frentes solicitadas'),
        ),
    ]
