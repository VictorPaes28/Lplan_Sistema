# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestao_aprovacao', '0010_add_solicitado_exclusao_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='workorder',
            name='motivo_exclusao',
            field=models.TextField(blank=True, help_text='Motivo informado pelo solicitante para exclusão do pedido', null=True, verbose_name='Motivo da Exclusão'),
        ),
    ]

