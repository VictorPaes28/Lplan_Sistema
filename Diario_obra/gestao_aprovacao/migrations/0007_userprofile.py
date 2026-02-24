# Generated manually

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('gestao_aprovacao', '0006_make_responsavel_optional'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('foto_perfil', models.ImageField(blank=True, help_text='Foto de perfil do usuário (opcional)', null=True, upload_to='perfis/', verbose_name='Foto de Perfil')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Última Atualização')),
                ('usuario', models.OneToOneField(help_text='Usuário associado a este perfil', on_delete=django.db.models.deletion.CASCADE, related_name='perfil', to=settings.AUTH_USER_MODEL, verbose_name='Usuário')),
            ],
            options={
                'verbose_name': 'Perfil de Usuário',
                'verbose_name_plural': 'Perfis de Usuário',
                'ordering': ['usuario__username'],
            },
        ),
    ]

