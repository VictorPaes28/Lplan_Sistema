from django.db import migrations


def corrigir_tipo_prazo(apps, schema_editor):
    PrazoContrato = apps.get_model('recursos_humanos', 'PrazoContrato')
    for prazo in PrazoContrato.objects.filter(tipo='experiencia'):
        dias = (prazo.data_fim - prazo.data_inicio).days
        if dias > 90:
            prazo.tipo = 'determinado'
            prazo.save(update_fields=['tipo'])


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0017_prazocontrato'),
    ]

    operations = [
        migrations.RunPython(corrigir_tipo_prazo, migrations.RunPython.noop),
    ]
