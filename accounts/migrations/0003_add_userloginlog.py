# Generated manually - UserLoginLog for analytics

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_delete_perfilusuario'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserLoginLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='login_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Registro de login',
                'verbose_name_plural': 'Registros de login',
                'ordering': ['-created_at'],
            },
        ),
    ]
