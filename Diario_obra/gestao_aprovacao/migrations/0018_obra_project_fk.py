# Migration: Obra.project -> core.Project (lista unica de obras no sistema)

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_add_project_member'),
        ('gestao_aprovacao', '0017_emaillog_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='obra',
            name='project',
            field=models.ForeignKey(
                blank=True,
                help_text='Projeto correspondente no Diario de Obra; se preenchido, acesso ao usuario e unificado.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='obras_gestao',
                to='core.Project',
                verbose_name='Projeto (Diario de Obra)',
            ),
        ),
    ]
