from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('comunicados', '0009_remove_tipo_confirmacao'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='comunicado',
            name='publico_restrito_perfil',
        ),
    ]
