# Seed: categorias e equipamentos padrão (pesquisa: equipamentos mais utilizados em obras - Brasloc, Guindastes Brasil, Construloc, SINAPI)

from django.db import migrations


def seed_equipment(apps, schema_editor):
    EquipmentCategory = apps.get_model('core', 'EquipmentCategory')
    StandardEquipment = apps.get_model('core', 'StandardEquipment')

    maquinas = EquipmentCategory.objects.create(slug='maquinas-veiculos', name='Máquinas e Veículos', order=1)
    canteiro = EquipmentCategory.objects.create(slug='canteiro', name='Equipamentos de Canteiro', order=2)

    # Ordem alfabética para facilitar localização pelo usuário
    maquinas_list = [
        'Caminhão basculante',
        'Caminhão betoneira',
        'Caminhão munck',
        'Empilhadeira',
        'Escavadeira',
        'Grua',
        'Guindaste',
        'Motoniveladora',
        'Pá carregadeira',
        'Placa vibratória',
        'Plataforma aérea',
        'Retroescavadeira',
        'Rolo compactador',
        'Trator de esteira',
    ]
    for i, name in enumerate(maquinas_list):
        StandardEquipment.objects.create(category=maquinas, name=name, order=i)

    canteiro_list = [
        'Andaime',
        'Betoneira',
        'Bomba de concreto',
        "Bomba d'água",
        'Compressora',
        'Container',
        'Escora metálica',
        'Furadeira',
        'Gerador de energia',
        'Martelete',
        'Serra de corte',
        'Vibrador de concreto',
    ]
    for i, name in enumerate(canteiro_list):
        StandardEquipment.objects.create(category=canteiro, name=name, order=i)


def reverse_seed(apps, schema_editor):
    StandardEquipment = apps.get_model('core', 'StandardEquipment')
    EquipmentCategory = apps.get_model('core', 'EquipmentCategory')
    StandardEquipment.objects.all().delete()
    EquipmentCategory.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_equipment_categories_standard'),
    ]

    operations = [
        migrations.RunPython(seed_equipment, reverse_seed),
    ]
