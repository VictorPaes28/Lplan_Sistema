from django.db import migrations, models


def migrar_tipo_confirmacao_para_texto(apps, schema_editor):
    Comunicado = apps.get_model('comunicados', 'Comunicado')
    Comunicado.objects.filter(tipo_conteudo='CONFIRMACAO').update(tipo_conteudo='TEXTO')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('comunicados', '0008_ajusta_limites_texto_usuario'),
    ]

    operations = [
        migrations.RunPython(
            migrar_tipo_confirmacao_para_texto,
            reverse_code=noop_reverse,
        ),
        migrations.AlterField(
            model_name='comunicado',
            name='tipo_conteudo',
            field=models.CharField(
                choices=[
                    ('TEXTO', 'Texto'),
                    ('IMAGEM', 'Imagem'),
                    ('IMAGEM_LINK', 'Imagem com link'),
                    ('FORMULARIO', 'Formulário'),
                ],
                default='TEXTO',
                max_length=32,
                verbose_name='Tipo de conteúdo',
            ),
        ),
        migrations.AlterField(
            model_name='comunicado',
            name='exige_resposta',
            field=models.BooleanField(
                default=False,
                help_text='Em Formulário: exige preencher/enviar a resposta antes de confirmar. Não combina com “Pode fechar” nem com “Permitir não mostrar novamente”.',
                verbose_name='Resposta obrigatória',
            ),
        ),
    ]
