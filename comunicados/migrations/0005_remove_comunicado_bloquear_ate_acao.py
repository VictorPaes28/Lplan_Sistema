# Generated manually — migra comportamento de bloquear_ate_acao para exige_resposta.

from django.db import migrations, models


def forwards_merge_bloquear_em_exige_resposta(apps, schema_editor):
    Comunicado = apps.get_model('comunicados', 'Comunicado')
    for c in Comunicado.objects.filter(
        tipo_conteudo__in=('FORMULARIO', 'CONFIRMACAO'),
        bloquear_ate_acao=True,
    ).iterator():
        if not c.exige_resposta:
            c.exige_resposta = True
            c.save(update_fields=['exige_resposta'])


class Migration(migrations.Migration):

    dependencies = [
        ('comunicados', '0004_merge_20260417_0915'),
    ]

    operations = [
        migrations.RunPython(forwards_merge_bloquear_em_exige_resposta, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='comunicado',
            name='exige_resposta',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Em Formulário ou Confirmação: exige preencher/enviar a resposta ou marcar ciência antes de confirmar; '
                    'enquanto ativo, não é possível fechar o modal até cumprir a ação.'
                ),
                verbose_name='Resposta obrigatória',
            ),
        ),
        migrations.RemoveField(
            model_name='comunicado',
            name='bloquear_ate_acao',
        ),
    ]
