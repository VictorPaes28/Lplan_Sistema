# Categoria ``bm`` removida do produto: processos e fluxos passam a ``medicao``.

from django.db import migrations


def _merge_bm_into_medicao(apps, schema_editor):
    ProcessCategory = apps.get_model('workflow_aprovacao', 'ProcessCategory')
    ApprovalFlowDefinition = apps.get_model('workflow_aprovacao', 'ApprovalFlowDefinition')
    ApprovalProcess = apps.get_model('workflow_aprovacao', 'ApprovalProcess')
    bm = ProcessCategory.objects.filter(code='bm').first()
    med = ProcessCategory.objects.filter(code='medicao').first()
    if not bm:
        return
    if not med:
        bm.delete()
        return
    ApprovalProcess.objects.filter(category_id=bm.pk).update(category_id=med.pk)
    for flow in list(ApprovalFlowDefinition.objects.filter(category_id=bm.pk)):
        clash = (
            ApprovalFlowDefinition.objects.filter(project_id=flow.project_id, category_id=med.pk)
            .exclude(pk=flow.pk)
            .first()
        )
        if clash:
            flow.delete()
        else:
            flow.category_id = med.pk
            flow.save(update_fields=['category_id'])
    bm.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('workflow_aprovacao', '0005_approvalprocess_external_payload'),
    ]

    operations = [
        migrations.RunPython(_merge_bm_into_medicao, migrations.RunPython.noop),
    ]
