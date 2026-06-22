from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0034_notificacao_enviada_tipo_alerta'),
    ]

    operations = [
        migrations.AddField(
            model_name='contratoadmissao',
            name='data_admissao_oficial',
            field=models.DateField(
                blank=True,
                help_text=(
                    'Data oficial de admissão informada na etapa do contrato (ZapSign). '
                    'Base para marcos D45/D90 do período de experiência CLT.'
                ),
                null=True,
                verbose_name='Data de admissão oficial',
            ),
        ),
    ]
