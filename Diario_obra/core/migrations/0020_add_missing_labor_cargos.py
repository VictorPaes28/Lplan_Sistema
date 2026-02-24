# Adiciona cargos faltantes conforme classificação mão de obra direta/indireta (construção civil)
# Referências: custos diretos/indiretos (Brickup, Escola Engenharia), CBO, administração da obra

from django.db import migrations


def add_missing_cargos(apps, schema_editor):
    LaborCategory = apps.get_model('core', 'LaborCategory')
    LaborCargo = apps.get_model('core', 'LaborCargo')

    try:
        indireta = LaborCategory.objects.get(slug='indireta')
    except LaborCategory.DoesNotExist:
        return

    # Indireta: Encarregado (supervisão no canteiro; fontes citam "encarregado de setor" como indireto)
    if not LaborCargo.objects.filter(category=indireta, name='Encarregado').exists():
        max_order = LaborCargo.objects.filter(category=indireta).order_by('-order').values_list('order', flat=True).first() or -1
        LaborCargo.objects.create(category=indireta, name='Encarregado', order=max_order + 1)

    try:
        direta = LaborCategory.objects.get(slug='direta')
    except LaborCategory.DoesNotExist:
        return

    # Direta: cargos de execução física (Brickup, CBO, tabelas construção civil)
    to_add_direta = [
        'Pintor',
        'Encanador',
        'Gesseiro',
        'Soldador',
    ]
    max_order = LaborCargo.objects.filter(category=direta).order_by('-order').values_list('order', flat=True).first() or -1
    for i, name in enumerate(to_add_direta):
        if not LaborCargo.objects.filter(category=direta, name=name).exists():
            max_order += 1
            LaborCargo.objects.create(category=direta, name=name, order=max_order)


def reverse_add(apps, schema_editor):
    LaborCategory = apps.get_model('core', 'LaborCategory')
    LaborCargo = apps.get_model('core', 'LaborCargo')
    names_indireta = ['Encarregado']
    names_direta = ['Pintor', 'Encanador', 'Gesseiro', 'Soldador']
    try:
        indireta = LaborCategory.objects.get(slug='indireta')
        LaborCargo.objects.filter(category=indireta, name__in=names_indireta).delete()
    except LaborCategory.DoesNotExist:
        pass
    try:
        direta = LaborCategory.objects.get(slug='direta')
        LaborCargo.objects.filter(category=direta, name__in=names_direta).delete()
    except LaborCategory.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0019_seed_labor_categories_cargos'),
    ]

    operations = [
        migrations.RunPython(add_missing_cargos, reverse_add),
    ]
