# Add work_stage (Status: Início, Andamento, Término) to DailyWorkLog

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_equipment_alphabetical_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailyworklog',
            name='work_stage',
            field=models.CharField(
                blank=True,
                choices=[('IN', 'Início'), ('AN', 'Andamento'), ('TE', 'Término')],
                default='AN',
                help_text='Estágio da atividade no dia',
                max_length=2,
                verbose_name='Status'
            ),
        ),
    ]
