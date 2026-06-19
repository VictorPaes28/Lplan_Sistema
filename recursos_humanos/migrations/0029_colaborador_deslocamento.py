from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0028_colaborador_portal_pin_hash'),
    ]

    operations = [
        migrations.AddField(
            model_name='colaborador',
            name='deslocamento_origem',
            field=models.CharField(
                blank=True,
                help_text='Local de origem do colaborador para deslocamento e reembolso de passagem.',
                max_length=120,
                verbose_name='Cidade de origem (de onde vem)',
            ),
        ),
        migrations.AddField(
            model_name='colaborador',
            name='deslocamento_destino',
            field=models.CharField(
                blank=True,
                help_text='Local de destino/alocação para deslocamento e reembolso de passagem.',
                max_length=120,
                verbose_name='Cidade de destino (para onde vai)',
            ),
        ),
    ]
