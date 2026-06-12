from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('recursos_humanos', '0009_colaborador_email_telefone'),
    ]

    operations = [
        migrations.AddField(
            model_name='colaborador',
            name='requisicao_criada_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='requisicoes_admissao_criadas',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Requisição criada por',
            ),
        ),
        migrations.AddField(
            model_name='colaborador',
            name='requisicao_motivo_reprovacao',
            field=models.TextField(blank=True, verbose_name='Motivo da reprovação da requisição'),
        ),
        migrations.AddField(
            model_name='colaborador',
            name='requisicao_reprovada',
            field=models.BooleanField(default=False, verbose_name='Requisição reprovada pelo gestor'),
        ),
    ]
