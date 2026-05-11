# Consolida administradores TrackHub/Central em «Administrador» (cadastro único na UI).

from django.db import migrations


_LEGACY_ADMIN_NAMES = (
    'TrackHub Administrador',
    'Central Aprovacoes Admin',
)
_CANON = 'Administrador'


def forwards(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')
    canon, _ = Group.objects.get_or_create(name=_CANON)
    legacy_groups = list(Group.objects.filter(name__in=_LEGACY_ADMIN_NAMES))
    if not legacy_groups:
        return
    legacy_ids = [g.pk for g in legacy_groups]
    qs = User.objects.filter(groups__id__in=legacy_ids).distinct()
    for u in qs.iterator(chunk_size=256):
        to_remove = []
        for g in legacy_groups:
            if u.groups.filter(pk=g.pk).exists():
                to_remove.append(g)
        if not to_remove:
            continue
        for g in to_remove:
            u.groups.remove(g)
        if not u.groups.filter(pk=canon.pk).exists():
            u.groups.add(canon)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_bi_map_controle_groups'),
    ]

    operations = [
        migrations.RunPython(forwards, noop_reverse),
    ]
