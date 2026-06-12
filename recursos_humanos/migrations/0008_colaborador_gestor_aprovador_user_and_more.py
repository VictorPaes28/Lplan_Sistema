from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('recursos_humanos', '0007_cargocatalogo'),
    ]

    operations = [
        migrations.AddField(
            model_name='colaborador',
            name='gestor_aprovador_user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='requisicoes_admissao_gestor',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Gestor aprovador (usuário)',
            ),
        ),
        migrations.AddField(
            model_name='colaborador',
            name='requisicao_aprovada_gestor',
            field=models.BooleanField(default=False, verbose_name='Requisição aprovada pelo gestor'),
        ),
    ]
