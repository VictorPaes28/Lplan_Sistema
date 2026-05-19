"""
Grupo operacional para envio de pedidos aprovados do GestControll à Central.

Sem permissões Django atribuídas — o papel é identificado apenas pela associação ao grupo.
"""

from django.db import migrations

GROUP_NAME = 'Enviar para Central de Aprovações'


def create_enviar_central_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name=GROUP_NAME)


def remove_enviar_central_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name=GROUP_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_unify_platform_admin_groups'),
    ]

    operations = [
        migrations.RunPython(create_enviar_central_group, remove_enviar_central_group),
    ]
