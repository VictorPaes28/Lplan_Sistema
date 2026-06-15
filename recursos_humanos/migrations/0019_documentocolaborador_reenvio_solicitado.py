from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0018_corrigir_tipo_prazo_experiencia'),
    ]

    operations = [
        migrations.AddField(
            model_name='documentocolaborador',
            name='reenvio_solicitado',
            field=models.BooleanField(
                default=False,
                help_text='RH solicitou novo envio; o arquivo atual permanece até o colaborador enviar outro.',
                verbose_name='Reenvio solicitado',
            ),
        ),
    ]
