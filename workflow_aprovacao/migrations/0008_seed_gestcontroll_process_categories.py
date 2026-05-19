"""
Garante ProcessCategory alinhadas aos tipos de WorkOrder.tipo_solicitacao do GestControll.

Códigos: contrato, validacao_contrato, medicao, ordem_servico, mapa_cotacao.
Usa update_or_create — não duplica categorias existentes.
"""

from django.db import migrations

# (code, name, sort_order) — mesmos códigos do GestControll
GESTCONTROLL_CATEGORIES = (
    ('contrato', 'Contrato', 10),
    ('validacao_contrato', 'Validação de Contrato', 15),
    ('medicao', 'Medição', 30),
    ('ordem_servico', 'Ordem de Serviço (OS)', 40),
    ('mapa_cotacao', 'Mapa de Cotação', 50),
)

# Apenas as criadas nesta migration (reversão não remove contrato/medicao legados)
NEW_CATEGORY_CODES = ('validacao_contrato', 'ordem_servico', 'mapa_cotacao')


def seed_gestcontroll_categories(apps, schema_editor):
    ProcessCategory = apps.get_model('workflow_aprovacao', 'ProcessCategory')
    for code, name, sort_order in GESTCONTROLL_CATEGORIES:
        ProcessCategory.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'is_active': True,
                'sort_order': sort_order,
            },
        )


def unseed_new_categories(apps, schema_editor):
    ProcessCategory = apps.get_model('workflow_aprovacao', 'ProcessCategory')
    ProcessCategory.objects.filter(code__in=NEW_CATEGORY_CODES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('workflow_aprovacao', '0007_alter_siengecentralsyncstate_options'),
    ]

    operations = [
        migrations.RunPython(seed_gestcontroll_categories, unseed_new_categories),
    ]
