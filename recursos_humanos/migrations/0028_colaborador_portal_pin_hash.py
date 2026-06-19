from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0027_alter_colaborador_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='colaborador',
            name='portal_pin_hash',
            field=models.CharField(
                blank=True,
                help_text='Hash do PIN de acesso ao portal (enviado por e-mail junto com o link).',
                max_length=128,
                verbose_name='PIN do portal (hash)',
            ),
        ),
    ]
