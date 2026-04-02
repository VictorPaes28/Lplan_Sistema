# Generated manually for sienge_codigos_alternativos on Project

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0034_supportticket_first_response_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='sienge_codigos_alternativos',
            field=models.TextField(
                blank=True,
                help_text=(
                    'Outros códigos de obra no Sienge que devem apontar para este projeto na importação MAPA '
                    '(ex.: MAPA envia 42 e o código principal da obra é 260). Separar por vírgula, ponto e vírgula ou linha.'
                ),
                verbose_name='Códigos Sienge alternativos (Mapa de suprimentos)',
            ),
        ),
    ]
