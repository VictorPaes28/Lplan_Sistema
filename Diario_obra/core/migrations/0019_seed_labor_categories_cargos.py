# Seed: Categorias e cargos padrão de mão de obra

from django.db import migrations


def seed_labor_categories_and_cargos(apps, schema_editor):
    LaborCategory = apps.get_model('core', 'LaborCategory')
    LaborCargo = apps.get_model('core', 'LaborCargo')

    indireta = LaborCategory.objects.create(slug='indireta', name='Mão de Obra Indireta', order=1)
    direta = LaborCategory.objects.create(slug='direta', name='Mão de Obra Direta', order=2)
    terceirizada = LaborCategory.objects.create(slug='terceirizada', name='Mão de Obra Terceirizada', order=3)

    cargos_indireta = [
        'Gerente de Obra',
        'Engenheiro(a) Civil',
        'Engenheiro(a) Controller / Qualidade',
        'Mestre de Obras',
        'Encarregado',
        'Técnico(a) de Edificações',
        'Técnico(a) de Segurança do Trabalho',
        'Supervisor(a) Administrativo',
        'Auxiliar Administrativo',
        'Profissional de RH',
        'Analista de Suprimentos',
        'Almoxarife',
        'Auxiliar de Almoxarifado',
        'Vigia',
    ]
    for i, name in enumerate(cargos_indireta):
        LaborCargo.objects.create(category=indireta, name=name, order=i)

    cargos_direta = [
        'Pedreiro',
        'Servente',
        'Carpinteiro',
        'Armador',
        'Eletricista',
        'Encanador',
        'Pintor',
        'Gesseiro',
        'Soldador',
        'Operador de Betoneira',
        'Operador de Retroescavadeira',
        'Ajudante Prático',
        'Serviços Gerais',
    ]
    for i, name in enumerate(cargos_direta):
        LaborCargo.objects.create(category=direta, name=name, order=i)

    cargos_terceirizada = [
        'Topógrafo',
        'Ajudante de Topografia',
        'Encarregado',
        'Operador de Máquina',
    ]
    for i, name in enumerate(cargos_terceirizada):
        LaborCargo.objects.create(category=terceirizada, name=name, order=i)


def reverse_seed(apps, schema_editor):
    LaborCargo = apps.get_model('core', 'LaborCargo')
    LaborCategory = apps.get_model('core', 'LaborCategory')
    LaborCargo.objects.all().delete()
    LaborCategory.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_labor_categories_and_entries'),
    ]

    operations = [
        migrations.RunPython(seed_labor_categories_and_cargos, reverse_seed),
    ]
