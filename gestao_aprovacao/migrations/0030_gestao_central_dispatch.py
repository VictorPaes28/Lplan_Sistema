import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('workflow_aprovacao', '0008_seed_gestcontroll_process_categories'),
        ('gestao_aprovacao', '0029_comment_origem'),
    ]

    operations = [
        migrations.CreateModel(
            name='GestaoCentralDispatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sent_at', models.DateTimeField(auto_now_add=True, verbose_name='Enviado em')),
                ('send_comment', models.TextField(blank=True, verbose_name='Observação do envio')),
                (
                    'snapshot_payload',
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text='Dados do pedido e referências de anexos no momento do envio.',
                    ),
                ),
                (
                    'approval_process',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='gestao_dispatch',
                        to='workflow_aprovacao.approvalprocess',
                        verbose_name='Processo na Central',
                    ),
                ),
                (
                    'sent_by',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='gestao_central_dispatches_sent',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Enviado por',
                    ),
                ),
                (
                    'work_order',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='central_dispatch',
                        to='gestao_aprovacao.workorder',
                        verbose_name='Pedido de obra',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Envio GestControll para Central',
                'verbose_name_plural': 'Envios GestControll para Central',
                'ordering': ['-sent_at'],
            },
        ),
    ]
