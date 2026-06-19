from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0025_tipodocumento_categoria_instrucoes_ativo'),
    ]

    operations = [
        migrations.AddField(
            model_name='colaborador',
            name='dados_coleta_solicitada',
            field=models.BooleanField(
                default=False,
                help_text='RH solicitou atualização dos dados pessoais no portal.',
                verbose_name='Dados pessoais solicitados no portal',
            ),
        ),
        migrations.AddField(
            model_name='documentocolaborador',
            name='coleta_solicitada',
            field=models.BooleanField(
                default=False,
                help_text='RH solicitou envio deste documento na coleta (portal restrito).',
                verbose_name='Coleta solicitada no portal',
            ),
        ),
    ]
