from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0030_colaborador_aprovadores_requisicao'),
    ]

    operations = [
        migrations.AddField(
            model_name='colaborador',
            name='reembolsos',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Lista de reembolsos previstos: título, descrição e valor.',
                verbose_name='Reembolsos previstos',
            ),
        ),
    ]
