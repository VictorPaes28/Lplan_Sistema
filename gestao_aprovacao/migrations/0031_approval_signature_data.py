from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestao_aprovacao', '0030_gestao_central_dispatch'),
    ]

    operations = [
        migrations.AddField(
            model_name='approval',
            name='signature_data',
            field=models.TextField(
                blank=True,
                help_text='Imagem PNG em base64 da assinatura do aprovador',
                null=True,
                verbose_name='Assinatura manual',
            ),
        ),
    ]
