from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0036_decisaoprazocontrato'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notificacaoenviada',
            name='tipo_alerta',
            field=models.CharField(
                choices=[
                    ('experiencia_45', 'Período de experiência — 45 dias'),
                    ('experiencia_90', 'Período de experiência — 90 dias'),
                    ('determinado_fim', 'Determinado — fim do prazo'),
                    ('estagio_fim', 'Estágio — fim do período'),
                    ('estagio_2anos', 'Estágio — limite 2 anos'),
                    ('pj_fim', 'PJ — fim do contrato'),
                    ('temporario_fim', 'Temporário — fim do prazo'),
                ],
                max_length=30,
                verbose_name='Tipo de alerta',
            ),
        ),
    ]
