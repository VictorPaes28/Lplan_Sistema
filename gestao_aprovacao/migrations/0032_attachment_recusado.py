from django.db import migrations, models


def marcar_recusados_pedidos_reprovados_sem_correcao(apps, schema_editor):
    """Pedidos reprovados só com anexos v0: marcar como recusados (fluxo legado)."""
    WorkOrder = apps.get_model('gestao_aprovacao', 'WorkOrder')
    Attachment = apps.get_model('gestao_aprovacao', 'Attachment')
    Approval = apps.get_model('gestao_aprovacao', 'Approval')

    for wo in WorkOrder.objects.filter(status='reprovado'):
        if not Approval.objects.filter(work_order=wo, decisao='reprovado').exists():
            continue
        if Attachment.objects.filter(work_order=wo, versao_reaprovacao__gt=0).exists():
            continue
        Attachment.objects.filter(work_order=wo, versao_reaprovacao=0).update(recusado=True)


class Migration(migrations.Migration):

    dependencies = [
        ('gestao_aprovacao', '0031_approval_signature_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='attachment',
            name='recusado',
            field=models.BooleanField(
                default=False,
                help_text='Documento recusado na reprovação — permanece para consulta e não entra no PDF do novo envio.',
                verbose_name='Recusado',
            ),
        ),
        migrations.RunPython(
            marcar_recusados_pedidos_reprovados_sem_correcao,
            migrations.RunPython.noop,
        ),
    ]
