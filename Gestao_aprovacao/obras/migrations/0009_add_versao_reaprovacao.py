# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('obras', '0008_notificacao'),
    ]

    operations = [
        migrations.AddField(
            model_name='attachment',
            name='versao_reaprovacao',
            field=models.IntegerField(default=0, help_text='Número da versão de reaprovação quando o anexo foi adicionado (0 = versão original)', verbose_name='Versão de Reaprovação'),
        ),
    ]

