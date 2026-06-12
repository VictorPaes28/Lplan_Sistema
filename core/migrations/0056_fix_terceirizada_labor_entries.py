# Corrige DiaryLaborEntry terceirizados salvos com cargo de equipe (direta/indireta).

from django.db import migrations


def fix_terceirizada_labor_entries(apps, schema_editor):
    from core.utils.diary_labor import fix_misclassified_terceirizada_labor_entries

    fix_misclassified_terceirizada_labor_entries()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0055_notification_rh_types'),
    ]

    operations = [
        migrations.RunPython(fix_terceirizada_labor_entries, noop_reverse),
    ]
