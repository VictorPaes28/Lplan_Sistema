# Generated migration - Add professional fields to ConstructionDiary

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='constructiondiary',
            name='temperature_min',
            field=models.IntegerField(blank=True, help_text='Temperatura mínima do dia em graus Celsius', null=True, verbose_name='Temperatura Mínima (°C)'),
        ),
        migrations.AddField(
            model_name='constructiondiary',
            name='temperature_max',
            field=models.IntegerField(blank=True, help_text='Temperatura máxima do dia em graus Celsius', null=True, verbose_name='Temperatura Máxima (°C)'),
        ),
        migrations.AddField(
            model_name='constructiondiary',
            name='work_hours',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Horas efetivas de trabalho (ex: 8.00, 7.50)', max_digits=4, null=True, verbose_name='Horas Trabalhadas'),
        ),
        migrations.AddField(
            model_name='constructiondiary',
            name='interruptions',
            field=models.TextField(blank=True, help_text='Registro de interrupções, paradas ou atrasos no trabalho', verbose_name='Interrupções/Paradas'),
        ),
        migrations.AddField(
            model_name='constructiondiary',
            name='incidents',
            field=models.TextField(blank=True, help_text='Registro de ocorrências, incidentes ou eventos relevantes do dia', verbose_name='Ocorrências/Incidentes'),
        ),
        migrations.AddField(
            model_name='constructiondiary',
            name='workers_present',
            field=models.IntegerField(blank=True, help_text='Quantidade de funcionários presentes no canteiro no dia', null=True, verbose_name='Número de Funcionários Presentes'),
        ),
    ]

