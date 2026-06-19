from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('recursos_humanos', '0031_colaborador_reembolsos'),
    ]

    operations = [
        migrations.AddField(
            model_name='colaborador',
            name='requisicao_aprovacao_assinatura',
            field=models.TextField(
                blank=True,
                help_text='PNG base64 da assinatura do aprovador na etapa 1.',
                verbose_name='Assinatura da aprovação da requisição',
            ),
        ),
        migrations.AddField(
            model_name='colaborador',
            name='requisicao_aprovada_em',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Requisição aprovada em',
            ),
        ),
        migrations.AddField(
            model_name='colaborador',
            name='requisicao_aprovada_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='requisicoes_admissao_aprovadas',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Requisição aprovada por',
            ),
        ),
    ]
