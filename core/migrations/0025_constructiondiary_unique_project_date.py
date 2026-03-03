# Garante um único diário por obra por dia (project + date)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_dailyworklog_work_stage'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='constructiondiary',
            unique_together={('project', 'date')},
        ),
    ]
