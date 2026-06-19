from django.db import migrations, models


def migrar_tipo_alerta(apps, schema_editor):
    NotificacaoEnviada = apps.get_model('recursos_humanos', 'NotificacaoEnviada')
    mapa = {45: 'experiencia_45', 90: 'experiencia_90'}
    for obj in NotificacaoEnviada.objects.all():
        obj.tipo_alerta = mapa.get(obj.marco, 'experiencia_45')
        obj.save(update_fields=['tipo_alerta'])


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0033_notificacao_enviada_experiencia'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='notificacaoenviada',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='notificacaoenviada',
            name='tipo_alerta',
            field=models.CharField(
                choices=[
                    ('experiencia_45', 'Experiência — 45 dias'),
                    ('experiencia_90', 'Experiência — 90 dias'),
                    ('determinado_fim', 'Determinado — fim do prazo'),
                    ('estagio_fim', 'Estágio — fim do período'),
                    ('estagio_2anos', 'Estágio — limite 2 anos'),
                    ('pj_fim', 'PJ — fim do contrato'),
                    ('temporario_fim', 'Temporário — fim do prazo'),
                ],
                max_length=30,
                null=True,
                verbose_name='Tipo de alerta',
            ),
        ),
        migrations.RunPython(migrar_tipo_alerta, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='notificacaoenviada',
            name='tipo_alerta',
            field=models.CharField(
                choices=[
                    ('experiencia_45', 'Experiência — 45 dias'),
                    ('experiencia_90', 'Experiência — 90 dias'),
                    ('determinado_fim', 'Determinado — fim do prazo'),
                    ('estagio_fim', 'Estágio — fim do período'),
                    ('estagio_2anos', 'Estágio — limite 2 anos'),
                    ('pj_fim', 'PJ — fim do contrato'),
                    ('temporario_fim', 'Temporário — fim do prazo'),
                ],
                max_length=30,
                verbose_name='Tipo de alerta',
            ),
        ),
        migrations.AlterField(
            model_name='notificacaoenviada',
            name='marco',
            field=models.PositiveSmallIntegerField(
                blank=True,
                choices=[(45, '45 dias'), (90, '90 dias')],
                help_text='Usado nos alertas de experiência (45/90).',
                null=True,
                verbose_name='Marco (dias)',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='notificacaoenviada',
            unique_together={('prazo_contrato', 'tipo_alerta', 'data_envio')},
        ),
        migrations.AlterModelOptions(
            name='notificacaoenviada',
            options={
                'ordering': ['-data_envio', '-pk'],
                'verbose_name': 'Notificação de contrato enviada',
                'verbose_name_plural': 'Notificações de contrato enviadas',
            },
        ),
    ]
