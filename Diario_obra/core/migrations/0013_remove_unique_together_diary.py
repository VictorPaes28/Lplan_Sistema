# Generated migration to remove unique_together constraint from ConstructionDiary
# This allows multiple reports (diaries) on the same day for the same project

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_update_labor_roles'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='constructiondiary',
            unique_together=set(),
        ),
    ]
