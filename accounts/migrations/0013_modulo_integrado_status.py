from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


MODULOS = (
    ('diario', 'Diário de Obra'),
    ('gestao', 'GestControll'),
    ('mapa', 'Mapa de Suprimentos'),
    ('workflow', 'Central de Aprovações'),
    ('trackhub', 'TrackHub'),
    ('impedimentos', 'Restrições'),
)


def seed_modulos(apps, schema_editor):
    ModuloIntegradoStatus = apps.get_model('accounts', 'ModuloIntegradoStatus')
    for codigo, nome in MODULOS:
        ModuloIntegradoStatus.objects.get_or_create(
            codigo=codigo,
            defaults={'nome': nome, 'ativo': True},
        )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0012_usersignuprequest_password_hash'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModuloIntegradoStatus',
            fields=[
                ('codigo', models.CharField(max_length=40, primary_key=True, serialize=False, verbose_name='Código')),
                ('nome', models.CharField(max_length=120, verbose_name='Nome')),
                ('ativo', models.BooleanField(default=True, verbose_name='Ativo')),
                ('mensagem', models.TextField(blank=True, help_text='Exibida quando o módulo está temporariamente indisponível.', verbose_name='Mensagem ao usuário')),
                ('previsao_retorno', models.DateField(blank=True, null=True, verbose_name='Previsão de retorno')),
                ('atualizado_em', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
                ('atualizado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='modulos_integrados_atualizados', to=settings.AUTH_USER_MODEL, verbose_name='Atualizado por')),
            ],
            options={
                'verbose_name': 'Status de módulo integrado',
                'verbose_name_plural': 'Status de módulos integrados',
            },
        ),
        migrations.RunPython(seed_modulos, migrations.RunPython.noop),
    ]
