from django.db import migrations, models


def forwards_migrar_tipos(apps, schema_editor):
    Comunicado = apps.get_model('comunicados', 'Comunicado')
    Comunicado.objects.filter(tipo_exibicao='ATE_CONFIRMAR').update(tipo_exibicao='SEMPRE')
    Comunicado.objects.filter(tipo_exibicao='X_VEZES').update(tipo_exibicao='UMA_VEZ')
    Comunicado.objects.filter(tipo_exibicao='X_DIAS').update(tipo_exibicao='SEMPRE')


class Migration(migrations.Migration):

    dependencies = [
        ('comunicados', '0010_remove_comunicado_publico_restrito_perfil'),
    ]

    operations = [
        migrations.RunPython(forwards_migrar_tipos, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='comunicado',
            name='tipo_exibicao',
            field=models.CharField(
                choices=[
                    ('SEMPRE', 'Sempre (a cada novo login)'),
                    ('UMA_VEZ', 'Uma vez por usuário'),
                    ('UMA_VEZ_POR_DIA', 'Uma vez por dia'),
                    ('ATE_RESPONDER', 'Até responder'),
                ],
                default='SEMPRE',
                max_length=32,
                verbose_name='Tipo de exibição',
            ),
        ),
        migrations.AlterField(
            model_name='comunicado',
            name='max_exibicoes_por_usuario',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Campo legado (não utilizado no painel).',
                null=True,
                verbose_name='Máx. exibições por usuário',
            ),
        ),
        migrations.AlterField(
            model_name='comunicado',
            name='dias_ativo',
            field=models.PositiveIntegerField(
                blank=True,
                help_text=(
                    'Janela opcional: com data de início, limita quantos dias o comunicado fica ativo '
                    '(independente do tipo de exibição).'
                ),
                null=True,
                verbose_name='Dias ativo',
            ),
        ),
    ]
