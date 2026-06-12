from django.db import migrations


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0002_seed_mvp_data'),
    ]

    operations = [
        migrations.RunPython(noop, noop),
    ]
