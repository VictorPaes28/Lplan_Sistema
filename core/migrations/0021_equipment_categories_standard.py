# EquipmentCategory e StandardEquipment para seleção no diário

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_add_missing_labor_cargos'),
    ]

    operations = [
        migrations.CreateModel(
            name='EquipmentCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(max_length=32, unique=True, verbose_name='Identificador')),
                ('name', models.CharField(max_length=100, verbose_name='Nome')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Ordem de exibição')),
            ],
            options={
                'verbose_name': 'Categoria de Equipamento',
                'verbose_name_plural': 'Categorias de Equipamento',
                'ordering': ['order', 'pk'],
            },
        ),
        migrations.CreateModel(
            name='StandardEquipment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, verbose_name='Nome')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Ordem de exibição')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='core.equipmentcategory', verbose_name='Categoria')),
            ],
            options={
                'verbose_name': 'Equipamento Padrão',
                'verbose_name_plural': 'Equipamentos Padrão',
                'ordering': ['category', 'order', 'name'],
                'unique_together': {('category', 'name')},
            },
        ),
    ]
