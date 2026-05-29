from django.db import migrations

GESTCONTROLL_CONFIGURAVEIS = (
    'gestcontroll.pedido_aprovado.solicitante',
    'gestcontroll.novo_pedido.aprovador',
    'gestcontroll.pedido_reprovado.solicitante',
)


def tornar_gestcontroll_configuravel(apps, schema_editor):
    TipoComunicacao = apps.get_model('core', 'TipoComunicacao')
    TipoComunicacao.objects.filter(codigo__in=GESTCONTROLL_CONFIGURAVEIS).update(
        obrigatorio=False,
        permite_usuario_desativar_email=True,
        permite_admin_desativar_email=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0046_cadastro_email_usuario_pode_desativar'),
    ]

    operations = [
        migrations.RunPython(tornar_gestcontroll_configuravel, migrations.RunPython.noop),
    ]
