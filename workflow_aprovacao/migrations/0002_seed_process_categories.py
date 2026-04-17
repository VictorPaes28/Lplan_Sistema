from django.db import migrations


def seed_categories(apps, schema_editor):
    ProcessCategory = apps.get_model('workflow_aprovacao', 'ProcessCategory')
    seed = [
        ('contrato', 'Contrato', 10),
        ('bm', 'BM', 20),
        ('medicao', 'Medição', 30),
    ]
    for code, name, order in seed:
        ProcessCategory.objects.update_or_create(
            code=code,
            defaults={'name': name, 'is_active': True, 'sort_order': order},
        )


def unseed(apps, schema_editor):
    ProcessCategory = apps.get_model('workflow_aprovacao', 'ProcessCategory')
    ProcessCategory.objects.filter(code__in=('contrato', 'bm', 'medicao')).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('workflow_aprovacao', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed),
    ]
