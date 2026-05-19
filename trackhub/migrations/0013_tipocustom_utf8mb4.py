from django.db import migrations


def ensure_utf8mb4(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE trackhub_tipocustom "
            "CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("trackhub", "0012_tipocustom_pendencia_tipo_maxlength"),
    ]

    operations = [
        migrations.RunPython(ensure_utf8mb4, migrations.RunPython.noop, atomic=False),
    ]
