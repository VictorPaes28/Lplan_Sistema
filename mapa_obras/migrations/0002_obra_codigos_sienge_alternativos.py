# Generated manually for Obra.codigos_sienge_alternativos

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mapa_obras', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='obra',
            name='codigos_sienge_alternativos',
            field=models.TextField(
                blank=True,
                help_text=(
                    'Outros códigos do Sienge que identificam a mesma obra (ex.: MAPA exporta 42 e o cadastro principal é 242). '
                    'Separar por vírgula, ponto e vírgula ou quebra de linha.'
                ),
            ),
        ),
    ]
