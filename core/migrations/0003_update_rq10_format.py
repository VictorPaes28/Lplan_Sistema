# Generated migration - Update to RQ-10 format

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_add_professional_fields'),
    ]

    operations = [
        # Remove temperature fields (not in RQ-10 format)
        migrations.RemoveField(
            model_name='constructiondiary',
            name='temperature_min',
        ),
        migrations.RemoveField(
            model_name='constructiondiary',
            name='temperature_max',
        ),
        migrations.RemoveField(
            model_name='constructiondiary',
            name='workers_present',
        ),
        # Add RQ-10 specific fields
        migrations.AddField(
            model_name='constructiondiary',
            name='rain_occurrence',
            field=models.CharField(blank=True, choices=[('', 'Nenhuma'), ('F', 'Fraca'), ('M', 'Média'), ('S', 'Forte')], default='', help_text='Intensidade de chuva no dia', max_length=1, verbose_name='Ocorrência de Chuvas'),
        ),
        migrations.AddField(
            model_name='constructiondiary',
            name='rain_observations',
            field=models.TextField(blank=True, help_text='Observações sobre ocorrência de chuvas', verbose_name='Observações sobre Chuvas'),
        ),
        migrations.AddField(
            model_name='constructiondiary',
            name='deliberations',
            field=models.TextField(blank=True, help_text='Deliberações e decisões tomadas no dia', verbose_name='Deliberações'),
        ),
        migrations.AddField(
            model_name='constructiondiary',
            name='inspection_responsible',
            field=models.CharField(blank=True, help_text='Nome do responsável pela inspeção diária', max_length=255, verbose_name='Responsável pela Inspeção Diária'),
        ),
        migrations.AddField(
            model_name='constructiondiary',
            name='production_responsible',
            field=models.CharField(blank=True, help_text='Nome do responsável pela produção', max_length=255, verbose_name='Responsável pela Produção'),
        ),
        # Update Labor model
        migrations.AddField(
            model_name='labor',
            name='labor_type',
            field=models.CharField(choices=[('I', 'Indireto (LPLAN)'), ('D', 'Direto'), ('T', 'Terceiros')], default='D', help_text='Tipo de efetivo: Indireto (LPLAN), Direto ou Terceiros', max_length=1, verbose_name='Tipo de Efetivo'),
        ),
        migrations.AddField(
            model_name='labor',
            name='company',
            field=models.CharField(blank=True, help_text='Nome da empresa terceirizada (se aplicável)', max_length=255, verbose_name='Empresa (Terceiros)'),
        ),
    ]

