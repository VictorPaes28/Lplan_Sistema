# Generated manually - Initial migration for core app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators
from decimal import Decimal


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=50, unique=True, verbose_name='Código do Projeto')),
                ('name', models.CharField(max_length=255, verbose_name='Nome do Projeto')),
                ('description', models.TextField(blank=True, verbose_name='Descrição')),
                ('start_date', models.DateField(verbose_name='Data de Início')),
                ('end_date', models.DateField(verbose_name='Data de Término')),
                ('is_active', models.BooleanField(default=True, verbose_name='Ativo')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Data de Atualização')),
            ],
            options={
                'verbose_name': 'Projeto',
                'verbose_name_plural': 'Projetos',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Activity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('path', models.CharField(max_length=255, unique=True)),
                ('depth', models.PositiveIntegerField()),
                ('numchild', models.PositiveIntegerField(default=0)),
                ('name', models.CharField(help_text='Nome descritivo da atividade', max_length=255, verbose_name='Nome da Atividade')),
                ('code', models.CharField(help_text='Código hierárquico da atividade (ex: "1.2.1")', max_length=100, verbose_name='Código da Atividade')),
                ('description', models.TextField(blank=True, help_text='Descrição detalhada da atividade', verbose_name='Descrição')),
                ('planned_start', models.DateField(blank=True, help_text='Data planejada de início da atividade', null=True, verbose_name='Início Planejado')),
                ('planned_end', models.DateField(blank=True, help_text='Data planejada de término da atividade', null=True, verbose_name='Término Planejado')),
                ('weight', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Peso da atividade para cálculo de progresso ponderado (0-100)', max_digits=5, validators=[django.core.validators.MinValueValidator(Decimal('0.00')), django.core.validators.MaxValueValidator(Decimal('100.00'))], verbose_name='Peso')),
                ('status', models.CharField(choices=[('NS', 'Não Iniciada'), ('IP', 'Em Andamento'), ('CO', 'Concluída'), ('BL', 'Bloqueada'), ('CA', 'Cancelada')], default='NS', help_text='Status atual da atividade', max_length=2, verbose_name='Status')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Data de Atualização')),
                ('project', models.ForeignKey(help_text='Projeto ao qual esta atividade pertence', on_delete=django.db.models.deletion.CASCADE, related_name='activities', to='core.project', verbose_name='Projeto')),
            ],
            options={
                'verbose_name': 'Atividade',
                'verbose_name_plural': 'Atividades',
                'ordering': ['code'],
            },
        ),
        migrations.CreateModel(
            name='ConstructionDiary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(help_text='Data do registro do diário', verbose_name='Data')),
                ('status', models.CharField(choices=[('PR', 'Preenchendo'), ('RV', 'Revisar'), ('AP', 'Aprovado')], default='PR', help_text='Status atual no workflow de aprovação', max_length=2, verbose_name='Status')),
                ('weather_conditions', models.TextField(blank=True, help_text='Descrição das condições climáticas do dia', verbose_name='Condições Climáticas')),
                ('general_notes', models.TextField(blank=True, help_text='Observações gerais sobre o dia de trabalho', verbose_name='Observações Gerais')),
                ('approved_at', models.DateTimeField(blank=True, help_text='Data e hora em que o diário foi aprovado', null=True, verbose_name='Data de Aprovação')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Data de Atualização')),
                ('created_by', models.ForeignKey(help_text='Engenheiro de campo que criou o diário', on_delete=django.db.models.deletion.PROTECT, related_name='created_diaries', to=settings.AUTH_USER_MODEL, verbose_name='Criado por')),
                ('project', models.ForeignKey(help_text='Projeto ao qual este diário pertence', on_delete=django.db.models.deletion.CASCADE, related_name='diaries', to='core.project', verbose_name='Projeto')),
                ('reviewed_by', models.ForeignKey(blank=True, help_text='Gerente que revisou o diário', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='reviewed_diaries', to=settings.AUTH_USER_MODEL, verbose_name='Revisado por')),
            ],
            options={
                'verbose_name': 'Diário de Obra',
                'verbose_name_plural': 'Diários de Obra',
                'ordering': ['-date', '-created_at'],
                'unique_together': {('project', 'date')},
            },
        ),
        migrations.CreateModel(
            name='DiaryImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(help_text='Arquivo de imagem original (alta resolução)', upload_to='diary_images/%Y/%m/%d/', verbose_name='Imagem')),
                ('pdf_optimized', models.ImageField(blank=True, help_text='Versão otimizada da imagem para geração de PDF (max 800px, JPEG, sem EXIF)', null=True, upload_to='diary_images/pdf_optimized/%Y/%m/%d/', verbose_name='Imagem Otimizada para PDF')),
                ('caption', models.CharField(blank=True, help_text='Legenda descritiva da foto', max_length=500, verbose_name='Legenda')),
                ('is_approved_for_report', models.BooleanField(default=True, help_text='Se False, a imagem não será incluída no PDF mas permanece no banco (preservação de evidência)', verbose_name='Aprovada para Relatório')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True, verbose_name='Data de Upload')),
                ('diary', models.ForeignKey(help_text='Diário de obra ao qual esta imagem pertence', on_delete=django.db.models.deletion.CASCADE, related_name='images', to='core.constructiondiary', verbose_name='Diário')),
            ],
            options={
                'verbose_name': 'Imagem do Diário',
                'verbose_name_plural': 'Imagens do Diário',
                'ordering': ['-uploaded_at'],
            },
        ),
        migrations.CreateModel(
            name='DailyWorkLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('percentage_executed_today', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Porcentagem da atividade executada neste dia específico (0-100)', max_digits=5, validators=[django.core.validators.MinValueValidator(Decimal('0.00')), django.core.validators.MaxValueValidator(Decimal('100.00'))], verbose_name='Porcentagem Executada Hoje')),
                ('accumulated_progress_snapshot', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Progresso acumulado total da atividade no momento deste registro', max_digits=5, validators=[django.core.validators.MinValueValidator(Decimal('0.00')), django.core.validators.MaxValueValidator(Decimal('100.00'))], verbose_name='Progresso Acumulado (Snapshot)')),
                ('notes', models.TextField(blank=True, help_text='Notas específicas sobre o trabalho realizado nesta atividade', verbose_name='Notas')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Data de Atualização')),
                ('activity', models.ForeignKey(help_text='Atividade da EAP relacionada a este registro', on_delete=django.db.models.deletion.CASCADE, related_name='work_logs', to='core.activity', verbose_name='Atividade')),
                ('diary', models.ForeignKey(help_text='Diário de obra ao qual este registro pertence', on_delete=django.db.models.deletion.CASCADE, related_name='work_logs', to='core.constructiondiary', verbose_name='Diário')),
            ],
            options={
                'verbose_name': 'Registro de Trabalho Diário',
                'verbose_name_plural': 'Registros de Trabalho Diário',
                'ordering': ['-created_at'],
                'unique_together': {('activity', 'diary')},
            },
        ),
        migrations.CreateModel(
            name='Labor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Nome do trabalhador ou função', max_length=255, verbose_name='Nome')),
                ('role', models.CharField(blank=True, help_text='Função ou cargo do trabalhador', max_length=100, verbose_name='Função')),
                ('hourly_rate', models.DecimalField(blank=True, decimal_places=2, help_text='Taxa horária de remuneração (opcional)', max_digits=10, null=True, verbose_name='Taxa Horária')),
                ('is_active', models.BooleanField(default=True, verbose_name='Ativo')),
            ],
            options={
                'verbose_name': 'Mão de Obra',
                'verbose_name_plural': 'Mão de Obra',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Equipment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Nome ou identificação do equipamento', max_length=255, verbose_name='Nome')),
                ('code', models.CharField(help_text='Código único do equipamento', max_length=50, unique=True, verbose_name='Código')),
                ('equipment_type', models.CharField(blank=True, help_text='Tipo de equipamento (ex: Escavadeira, Betoneira)', max_length=100, verbose_name='Tipo')),
                ('is_active', models.BooleanField(default=True, verbose_name='Ativo')),
            ],
            options={
                'verbose_name': 'Equipamento',
                'verbose_name_plural': 'Equipamentos',
                'ordering': ['code'],
            },
        ),
        migrations.AddIndex(
            model_name='activity',
            index=models.Index(fields=['project', 'code'], name='core_activ_project_idx'),
        ),
        migrations.AddIndex(
            model_name='activity',
            index=models.Index(fields=['project', 'status'], name='core_activ_project_status_idx'),
        ),
        migrations.AddIndex(
            model_name='constructiondiary',
            index=models.Index(fields=['project', 'date'], name='core_const_project_date_idx'),
        ),
        migrations.AddIndex(
            model_name='constructiondiary',
            index=models.Index(fields=['project', 'status'], name='core_const_project_status_idx'),
        ),
        migrations.AddIndex(
            model_name='constructiondiary',
            index=models.Index(fields=['status', '-date'], name='core_const_status_date_idx'),
        ),
        migrations.AddIndex(
            model_name='diaryimage',
            index=models.Index(fields=['diary', 'is_approved_for_report'], name='core_diary_diary_approv_idx'),
        ),
        migrations.AddIndex(
            model_name='equipment',
            index=models.Index(fields=['code'], name='core_equip_code_idx'),
        ),
        migrations.AddIndex(
            model_name='dailyworklog',
            index=models.Index(fields=['activity', 'diary'], name='core_dailyw_activity_diary_idx'),
        ),
        migrations.AddIndex(
            model_name='dailyworklog',
            index=models.Index(fields=['diary', '-created_at'], name='core_dailyw_diary_created_idx'),
        ),
        migrations.AddField(
            model_name='dailyworklog',
            name='resources_labor',
            field=models.ManyToManyField(blank=True, help_text='Trabalhadores envolvidos nesta atividade', related_name='work_logs', to='core.labor', verbose_name='Mão de Obra'),
        ),
        migrations.AddField(
            model_name='dailyworklog',
            name='resources_equipment',
            field=models.ManyToManyField(blank=True, help_text='Equipamentos utilizados nesta atividade', related_name='work_logs', to='core.equipment', verbose_name='Equipamentos'),
        ),
    ]

