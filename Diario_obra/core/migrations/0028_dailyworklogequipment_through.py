# Generated manually - Through model for equipment quantity
# Se esta migração falhou antes (AlterField) e a tabela core_dailyworklogequipment já existe,
# rode no banco: DROP TABLE core_dailyworklogequipment; depois: python manage.py migrate core

from django.db import migrations, models
import django.db.models.deletion


def copy_equipment_to_through(apps, schema_editor):
    """Copia dados da M2M antiga para DailyWorkLogEquipment com quantity=1."""
    DailyWorkLog = apps.get_model('core', 'DailyWorkLog')
    DailyWorkLogEquipment = apps.get_model('core', 'DailyWorkLogEquipment')
    if DailyWorkLogEquipment.objects.exists():
        return  # Já foi copiado (reexecução da migração)
    for wl in DailyWorkLog.objects.all():
        for eq in wl.resources_equipment.all():
            DailyWorkLogEquipment.objects.get_or_create(
                work_log=wl,
                equipment=eq,
                defaults={'quantity': 1},
            )


def noop_reverse(apps, schema_editor):
    """Não é possível reverter a cópia de forma segura."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0027_rename_core_diaryco_diary_i_9f2a3b_idx_core_diaryc_diary_i_e65c0f_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='DailyWorkLogEquipment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=1, help_text='Número de unidades utilizadas', verbose_name='Quantidade')),
                ('equipment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='work_log_through', to='core.equipment', verbose_name='Equipamento')),
                ('work_log', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='equipment_through', to='core.dailyworklog', verbose_name='Registro de trabalho')),
            ],
            options={
                'verbose_name': 'Equipamento do registro de trabalho',
                'verbose_name_plural': 'Equipamentos do registro de trabalho',
                'unique_together': {('work_log', 'equipment')},
            },
        ),
        migrations.RunPython(copy_equipment_to_through, noop_reverse),
        migrations.RemoveField(
            model_name='dailyworklog',
            name='resources_equipment',
        ),
        migrations.AddField(
            model_name='dailyworklog',
            name='resources_equipment',
            field=models.ManyToManyField(
                blank=True,
                help_text='Equipamentos utilizados nesta atividade',
                related_name='work_logs',
                through='core.DailyWorkLogEquipment',
                through_fields=('work_log', 'equipment'),
                to='core.equipment',
                verbose_name='Equipamentos',
            ),
        ),
    ]
