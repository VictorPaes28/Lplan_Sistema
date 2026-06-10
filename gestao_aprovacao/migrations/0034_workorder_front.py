from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0032_alter_constructiondiary_status_diaryapprovalhistory_and_more'),
        ('gestao_aprovacao', '0033_alter_aprovacaoemaildestinatario_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='workorder',
            name='front',
            field=models.ForeignKey(
                blank=True,
                help_text='Frente da obra para este pedido (opcional para admins).',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='work_orders_gestao',
                to='core.projectfront',
                verbose_name='Frente',
            ),
        ),
    ]
