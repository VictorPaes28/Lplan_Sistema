from django.db import migrations


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(noop, noop),
    ]
