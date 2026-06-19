from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('recursos_humanos', '0029_colaborador_deslocamento'),
    ]

    operations = [
        migrations.AddField(
            model_name='colaborador',
            name='aprovadores_requisicao',
            field=models.ManyToManyField(
                blank=True,
                related_name='requisicoes_admissao_aprovador',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Aprovadores da requisição',
            ),
        ),
    ]
