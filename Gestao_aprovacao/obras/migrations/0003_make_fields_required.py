# Generated manually to make fields required after initial migration

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('obras', '0002_approval_attachment_obra_statushistory_and_more'),
    ]

    operations = [
        # Tornar obra obrigatório
        migrations.AlterField(
            model_name='workorder',
            name='obra',
            field=models.ForeignKey(
                help_text='Obra à qual este pedido pertence',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='work_orders',
                to='obras.obra',
                verbose_name='Obra'
            ),
        ),
        # Tornar nome_credor obrigatório
        migrations.AlterField(
            model_name='workorder',
            name='nome_credor',
            field=models.CharField(
                help_text='Nome do fornecedor/credor relacionado ao pedido',
                max_length=200,
                verbose_name='Nome do Credor'
            ),
        ),
        # Tornar tipo_solicitacao obrigatório
        migrations.AlterField(
            model_name='workorder',
            name='tipo_solicitacao',
            field=models.CharField(
                choices=[('contrato', 'Contrato'), ('medicao', 'Medição')],
                help_text='Tipo de solicitação: Contrato ou Medição',
                max_length=20,
                verbose_name='Tipo de Solicitação'
            ),
        ),
    ]

