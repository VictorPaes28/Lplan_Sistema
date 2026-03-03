# Generated manually
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_notification_diaryvideo_diaryattachment'),
    ]

    operations = [
        migrations.CreateModel(
            name='OccurrenceTag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Nome da tag/categoria (ex: "Atraso", "Material", "Segurança")', max_length=100, unique=True, verbose_name='Nome da Tag')),
                ('color', models.CharField(default='#3B82F6', help_text='Cor da tag em hexadecimal (ex: #3B82F6)', max_length=7, verbose_name='Cor')),
                ('is_active', models.BooleanField(default=True, help_text='Indica se a tag está ativa e pode ser usada', verbose_name='Ativa')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')),
            ],
            options={
                'verbose_name': 'Tag de Ocorrência',
                'verbose_name_plural': 'Tags de Ocorrências',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='DiaryOccurrence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.TextField(help_text='Descrição detalhada da ocorrência', verbose_name='Descrição')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Data de Atualização')),
                ('created_by', models.ForeignKey(help_text='Usuário que registrou a ocorrência', on_delete=django.db.models.deletion.PROTECT, related_name='created_occurrences', to='auth.user', verbose_name='Criado por')),
                ('diary', models.ForeignKey(help_text='Diário de obra ao qual esta ocorrência pertence', on_delete=django.db.models.deletion.CASCADE, related_name='occurrences', to='core.constructiondiary', verbose_name='Diário')),
                ('tags', models.ManyToManyField(blank=True, help_text='Tags/categorias associadas a esta ocorrência', related_name='occurrences', to='core.occurrencetag', verbose_name='Tags')),
            ],
            options={
                'verbose_name': 'Ocorrência',
                'verbose_name_plural': 'Ocorrências',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='occurrencetag',
            index=models.Index(fields=['is_active', 'name'], name='core_occurr_is_acti_123456_idx'),
        ),
        migrations.AddIndex(
            model_name='diaryoccurrence',
            index=models.Index(fields=['diary', '-created_at'], name='core_diaryoc_diary_i_123456_idx'),
        ),
    ]

