from django.db import migrations


def forwards(apps, schema_editor):
    ItemMapa = apps.get_model('suprimentos', 'ItemMapa')
    # Descontinuado: garantir que nenhum item fique marcado como "não aplica"
    ItemMapa.objects.filter(nao_aplica=True).update(nao_aplica=False)


def backwards(apps, schema_editor):
    # Não reverte
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('suprimentos', '0008_historico_alteracoes'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]


