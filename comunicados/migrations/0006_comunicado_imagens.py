# Generated manually — várias imagens por comunicado (máx. 5 na app).

from django.db import migrations, models
import django.db.models.deletion


def forwards_copiar_imagem_para_relacao(apps, schema_editor):
    Comunicado = apps.get_model('comunicados', 'Comunicado')
    ComunicadoImagem = apps.get_model('comunicados', 'ComunicadoImagem')
    for c in Comunicado.objects.iterator():
        if c.imagem:
            ComunicadoImagem.objects.create(comunicado_id=c.pk, arquivo=c.imagem, ordem=0)


class Migration(migrations.Migration):

    dependencies = [
        ('comunicados', '0005_remove_comunicado_bloquear_ate_acao'),
    ]

    operations = [
        migrations.CreateModel(
            name='ComunicadoImagem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('arquivo', models.ImageField(upload_to='comunicados/', verbose_name='Ficheiro')),
                ('ordem', models.PositiveSmallIntegerField(default=0, verbose_name='Ordem')),
                (
                    'comunicado',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='imagens',
                        to='comunicados.comunicado',
                        verbose_name='Comunicado',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Imagem do comunicado',
                'verbose_name_plural': 'Imagens do comunicado',
                'ordering': ['ordem', 'pk'],
            },
        ),
        migrations.RunPython(forwards_copiar_imagem_para_relacao, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='comunicado',
            name='imagem',
        ),
    ]
