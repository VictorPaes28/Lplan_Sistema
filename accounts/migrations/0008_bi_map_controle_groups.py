# Garantir grupos dedicados ao Mapa de Controle e ao BI da Obra; preservar comportamento herdado.

from django.db import migrations


def forwards(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')

    g_mc, _ = Group.objects.get_or_create(name='Mapa de Controle')
    g_bi, _ = Group.objects.get_or_create(name='BI da Obra')
    nome_sup = 'Mapa de Suprimentos'
    usuarios = User.objects.filter(groups__name=nome_sup).distinct()
    for u in usuarios.iterator():
        u.groups.add(g_mc, g_bi)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_userloginlog_ip_user_agent'),
    ]

    operations = [
        migrations.RunPython(forwards, noop_reverse),
    ]
