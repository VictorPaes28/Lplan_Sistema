# Generated manually - vínculo usuário–obra no Diário de Obra

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0015_backend_improvements'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='members', to='core.project', verbose_name='Obra / Projeto')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='diario_project_memberships', to=settings.AUTH_USER_MODEL, verbose_name='Usuário')),
            ],
            options={
                'verbose_name': 'Vínculo usuário–obra (Diário)',
                'verbose_name_plural': 'Vínculos usuário–obra (Diário)',
                'unique_together': {('user', 'project')},
            },
        ),
    ]
