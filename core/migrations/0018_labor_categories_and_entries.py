# Generated - LaborCategory, LaborCargo, DiaryLaborEntry

from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_add_project_diary_recipient'),
    ]

    operations = [
        migrations.CreateModel(
            name='LaborCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(max_length=32, unique=True, verbose_name='Identificador')),
                ('name', models.CharField(max_length=100, verbose_name='Nome')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Ordem de exibição')),
            ],
            options={
                'verbose_name': 'Categoria de Mão de Obra',
                'verbose_name_plural': 'Categorias de Mão de Obra',
                'ordering': ['order', 'pk'],
            },
        ),
        migrations.CreateModel(
            name='LaborCargo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, verbose_name='Nome do cargo')),
                ('order', models.PositiveSmallIntegerField(default=0, verbose_name='Ordem de exibição')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cargos', to='core.laborcategory', verbose_name='Categoria')),
            ],
            options={
                'verbose_name': 'Cargo (Mão de Obra)',
                'verbose_name_plural': 'Cargos (Mão de Obra)',
                'ordering': ['category', 'order', 'name'],
                'unique_together': {('category', 'name')},
            },
        ),
        migrations.CreateModel(
            name='DiaryLaborEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveSmallIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)], verbose_name='Quantidade')),
                ('company', models.CharField(blank=True, help_text='Nome da empresa terceirizada; preencher apenas para mão de obra terceirizada', max_length=255, verbose_name='Empresa (Terceirizada)')),
                ('cargo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='diary_entries', to='core.laborcargo', verbose_name='Cargo')),
                ('diary', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='labor_entries', to='core.constructiondiary', verbose_name='Diário')),
            ],
            options={
                'verbose_name': 'Registro de Mão de Obra no Diário',
                'verbose_name_plural': 'Registros de Mão de Obra no Diário',
                'ordering': ['diary', 'company', 'cargo'],
            },
        ),
    ]
