from django.db import migrations

from recursos_humanos.seed_exemplos_quadro import seed_exemplos_quadro, unseed_exemplos_quadro


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0022_papeis_fluxo_admissao'),
    ]

    operations = [
        migrations.RunPython(seed_exemplos_quadro, unseed_exemplos_quadro),
    ]
