# Garante utf8mb4 na coluna observacao (evita MySQL 1366 com texto Unicode / NFD).

from django.db import migrations


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return
    sql = """
    ALTER TABLE gestao_aprovacao_statushistory
    MODIFY observacao LONGTEXT
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL;
    """
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql)


def backwards(apps, schema_editor):
    # Reversão não restaura charset antigo (evita recriar problema).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('gestao_aprovacao', '0021_alter_emaillog_tipo_email'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
