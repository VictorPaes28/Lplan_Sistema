# Dono da obra: ProjectOwner, comentários no diário (DiaryComment), janela 24h (sent_to_owner_at)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0025_constructiondiary_unique_project_date'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectOwner',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='owners', to='core.project', verbose_name='Obra')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='owned_projects', to=settings.AUTH_USER_MODEL, verbose_name='Dono (usuário)')),
            ],
            options={
                'verbose_name': 'Dono da Obra',
                'verbose_name_plural': 'Donos da Obra',
                'unique_together': {('project', 'user')},
            },
        ),
        migrations.AddField(
            model_name='constructiondiary',
            name='sent_to_owner_at',
            field=models.DateTimeField(blank=True, help_text='Data/hora em que o diário foi enviado ao dono da obra (início da janela de 24h para comentários)', null=True, verbose_name='Enviado ao dono em'),
        ),
        migrations.CreateModel(
            name='DiaryComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField(verbose_name='Comentário')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Data')),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='diary_comments', to=settings.AUTH_USER_MODEL, verbose_name='Autor')),
                ('diary', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='owner_comments', to='core.constructiondiary', verbose_name='Diário')),
            ],
            options={
                'verbose_name': 'Comentário no diário (cliente/LPLAN)',
                'verbose_name_plural': 'Comentários no diário',
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='projectowner',
            index=models.Index(fields=['user'], name='core_projec_user_id_7e2b0d_idx'),
        ),
        migrations.AddIndex(
            model_name='projectowner',
            index=models.Index(fields=['project'], name='core_projec_project_8a3f1e_idx'),
        ),
        migrations.AddIndex(
            model_name='diarycomment',
            index=models.Index(fields=['diary'], name='core_diaryco_diary_i_9f2a3b_idx'),
        ),
    ]
