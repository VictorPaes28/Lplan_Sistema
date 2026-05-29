from django.db import migrations


def habilitar_cadastro_preferencia_usuario(apps, schema_editor):
    TipoComunicacao = apps.get_model('core', 'TipoComunicacao')
    TipoComunicacao.objects.filter(codigo='cadastro.nova_solicitacao_admin').update(
        permite_usuario_desativar_email=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0045_seed_padroes_grupo_comunicacao'),
    ]

    operations = [
        migrations.RunPython(habilitar_cadastro_preferencia_usuario, migrations.RunPython.noop),
    ]
