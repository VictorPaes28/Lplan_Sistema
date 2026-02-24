# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestao_aprovacao', '0013_add_lembrete_model'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lembrete',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('pendente_1_dia', 'Pendente há 1 dia'),
                    ('pendente_2_dias', 'Pendente há 2 dias'),
                    ('pendente_3_dias', 'Pendente há 3 dias'),
                    ('pendente_5_dias', 'Pendente há 5 dias'),
                    ('pendente_7_dias', 'Pendente há 7 dias'),
                    ('pendente_10_dias', 'Pendente há 10 dias'),
                    ('pendente_15_dias', 'Pendente há 15 dias'),
                    ('pendente_20_dias', 'Pendente há 20 dias'),
                    ('pendente_30_dias', 'Pendente há 30 dias'),
                ],
                help_text='Tipo de lembrete enviado',
                max_length=50,
                verbose_name='Tipo de Lembrete'
            ),
        ),
    ]

