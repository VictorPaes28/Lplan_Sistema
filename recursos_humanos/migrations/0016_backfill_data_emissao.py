from datetime import timedelta

from django.db import migrations


def backfill_data_emissao(apps, schema_editor):
    DocumentoColaborador = apps.get_model('recursos_humanos', 'DocumentoColaborador')
    TipoDocumento = apps.get_model('recursos_humanos', 'TipoDocumento')

    docs = DocumentoColaborador.objects.filter(
        vencimento__isnull=False,
        data_emissao__isnull=True,
    )
    for doc in docs.iterator():
        try:
            tipo = TipoDocumento.objects.get(pk=doc.tipo_id)
        except TipoDocumento.DoesNotExist:
            continue
        if tipo.tem_validade and tipo.dias_validade:
            doc.data_emissao = doc.vencimento - timedelta(days=tipo.dias_validade)
            doc.save(update_fields=['data_emissao'])


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0015_documentocolaborador_data_emissao'),
    ]

    operations = [
        migrations.RunPython(backfill_data_emissao, migrations.RunPython.noop),
    ]
