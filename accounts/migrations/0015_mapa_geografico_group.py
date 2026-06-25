"""Grupo dedicado ao Mapa Geográfico (UI de permissões e cadastros)."""

from django.db import migrations

GROUP_NAME = 'Mapa Geográfico'
LEGACY_DIARIO = 'Diário de Obra'


def forwards(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')
    g_geo, _ = Group.objects.get_or_create(name=GROUP_NAME)
    for user in User.objects.filter(groups__name=LEGACY_DIARIO).distinct().iterator():
        user.groups.add(g_geo)


def backwards(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name=GROUP_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0014_usersignuprequest_requested_front_ids'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
