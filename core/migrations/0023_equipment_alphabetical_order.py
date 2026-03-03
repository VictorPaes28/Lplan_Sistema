# Reordena equipamentos em ordem alfabética dentro de cada categoria

from django.db import migrations


def reorder_equipment(apps, schema_editor):
    StandardEquipment = apps.get_model('core', 'StandardEquipment')
    from collections import defaultdict
    by_category = defaultdict(list)
    for item in StandardEquipment.objects.order_by('category_id', 'name'):
        by_category[item.category_id].append(item)
    for category_id, items in by_category.items():
        for i, item in enumerate(items):
            item.order = i
            item.save(update_fields=['order'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_seed_equipment_categories'),
    ]

    operations = [
        migrations.RunPython(reorder_equipment, noop),
    ]
