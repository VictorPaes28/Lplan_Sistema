from django.db import migrations


NOVOS_CODIGOS = {
    'cadastro.solicitacao_reprovada_solicitante',
    'trackhub.notificacao_etapa.email',
}


def seed_tipos_complementares(apps, schema_editor):
    TipoComunicacao = apps.get_model('core', 'TipoComunicacao')
    from core.comunicacao_constants import TIPOS_COMUNICACAO_SEED

    for row in TIPOS_COMUNICACAO_SEED:
        if row['codigo'] not in NOVOS_CODIGOS:
            continue
        TipoComunicacao.objects.update_or_create(
            codigo=row['codigo'],
            defaults=row,
        )


def unseed_tipos_complementares(apps, schema_editor):
    TipoComunicacao = apps.get_model('core', 'TipoComunicacao')
    TipoComunicacao.objects.filter(codigo__in=NOVOS_CODIGOS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0047_gestcontroll_emails_configuraveis'),
    ]

    operations = [
        migrations.RunPython(seed_tipos_complementares, unseed_tipos_complementares),
    ]
