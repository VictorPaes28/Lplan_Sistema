# Generated manually — seed padrões iniciais por grupo

from django.db import migrations


def seed_padroes_grupo(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    TipoComunicacao = apps.get_model('core', 'TipoComunicacao')
    PadraoComunicacaoGrupo = apps.get_model('core', 'PadraoComunicacaoGrupo')

    from core.comunicacao_constants import PADROES_GRUPO_SEED

    for item in PADROES_GRUPO_SEED:
        grupo = Group.objects.filter(name=item['grupo']).first()
        if not grupo:
            continue
        tipo = TipoComunicacao.objects.filter(codigo=item['tipo_codigo']).first()
        if not tipo:
            continue
        PadraoComunicacaoGrupo.objects.update_or_create(
            grupo=grupo,
            tipo=tipo,
            defaults={
                'email_ativo': item['email_ativo'],
                'interno_ativo': None,
                'resumo_ativo': False,
            },
        )


def unseed_padroes_grupo(apps, schema_editor):
    PadraoComunicacaoGrupo = apps.get_model('core', 'PadraoComunicacaoGrupo')
    from core.comunicacao_constants import PADROES_GRUPO_SEED

    codigos = {item['tipo_codigo'] for item in PADROES_GRUPO_SEED}
    PadraoComunicacaoGrupo.objects.filter(tipo__codigo__in=codigos).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0044_comunicacao_preferencias'),
    ]

    operations = [
        migrations.RunPython(seed_padroes_grupo, unseed_padroes_grupo),
    ]
