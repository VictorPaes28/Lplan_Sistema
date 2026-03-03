# Migração de dados: renomeia grupos antigos para os novos nomes
# Gerentes -> Diário de Obra
# ENGENHARIA -> Mapa de Suprimentos

from django.db import migrations


def rename_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    # Renomear para os nomes que o código passa a usar (accounts.groups.GRUPOS)
    for old_name, new_name in [('Gerentes', 'Diário de Obra'), ('ENGENHARIA', 'Mapa de Suprimentos')]:
        Group.objects.filter(name=old_name).update(name=new_name)


def reverse_rename(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for new_name, old_name in [('Diário de Obra', 'Gerentes'), ('Mapa de Suprimentos', 'ENGENHARIA')]:
        Group.objects.filter(name=new_name).update(name=old_name)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_add_userloginlog'),
    ]

    operations = [
        migrations.RunPython(rename_grupos, reverse_rename),
    ]
