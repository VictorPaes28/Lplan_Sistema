from django.db import migrations

from recursos_humanos.seed_corrigir_dossie_quadro import corrigir_dossie_quadro, noop_reverse


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0023_seed_exemplos_quadro'),
    ]

    operations = [
        migrations.RunPython(corrigir_dossie_quadro, noop_reverse),
    ]
