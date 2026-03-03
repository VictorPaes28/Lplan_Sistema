# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_add_occurrence_tags'),
    ]

    operations = [
        migrations.AlterField(
            model_name='labor',
            name='role',
            field=models.CharField(
                choices=[
                    ('AJ', 'Ajudante'),
                    ('EL', 'Eletricista'),
                    ('EN', 'Engenheiro'),
                    ('ES', 'Estagiário'),
                    ('GE', 'Gesseiro'),
                    ('ME', 'Mestre de Obra'),
                    ('PE', 'Pedreiro'),
                    ('SE', 'Servente'),
                    ('TE', 'Técnico em Edificações'),
                    ('CA', 'Carpinteiro'),
                    ('HI', 'Hidráulico'),
                    ('AR', 'Armador'),
                    ('OU', 'Outro'),
                ],
                default='OU',
                help_text='Categoria ou função do trabalhador',
                max_length=3,
                verbose_name='Função/Categoria'
            ),
        ),
    ]

