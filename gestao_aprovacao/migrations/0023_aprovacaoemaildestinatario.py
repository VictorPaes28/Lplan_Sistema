# Generated manually for configurable GestControll approval email recipients.

from django.db import migrations, models


def seed_destinatarios_padrao(apps, schema_editor):
    M = apps.get_model('gestao_aprovacao', 'AprovacaoEmailDestinatario')
    seed = [
        ('luiz.henrique@lplan.com.br', 'Luiz Henrique', 0),
        ('luizdomingos@lplan.com.br', 'Luiz Domingos', 1),
    ]
    for email, nome, ordem in seed:
        M.objects.get_or_create(
            email=email,
            defaults={'nome': nome, 'ordem': ordem, 'ativo': True},
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('gestao_aprovacao', '0022_fix_statushistory_observacao_charset'),
    ]

    operations = [
        migrations.CreateModel(
            name='AprovacaoEmailDestinatario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(help_text='Recebe cópia do e-mail de pedido aprovado (com anexos PDF quando houver).', max_length=254, unique=True, verbose_name='E-mail')),
                ('nome', models.CharField(blank=True, help_text='Ex.: identificação interna do destinatário.', max_length=120, verbose_name='Nome (opcional)')),
                ('ativo', models.BooleanField(default=True, help_text='Se desmarcado, não entra nos envios.', verbose_name='Ativo')),
                ('ordem', models.PositiveSmallIntegerField(default=0, help_text='Menor valor aparece primeiro na lista.', verbose_name='Ordem')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Cadastrado em')),
            ],
            options={
                'verbose_name': 'Destinatário de e-mail de pedido aprovado',
                'verbose_name_plural': 'Destinatários de e-mail de pedidos aprovados',
                'ordering': ['ordem', 'email'],
            },
        ),
        migrations.RunPython(seed_destinatarios_padrao, noop_reverse),
    ]
