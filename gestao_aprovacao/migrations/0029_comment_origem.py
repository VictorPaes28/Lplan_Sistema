# Generated manually for separating manual comments from system records.

from django.db import migrations, models


def forwards_classify_reprovacao_comments(apps, schema_editor):
    Comment = apps.get_model('gestao_aprovacao', 'Comment')
    Comment.objects.filter(texto__startswith='[Reprovação]').update(origem='sistema')


class Migration(migrations.Migration):

    dependencies = [
        ('gestao_aprovacao', '0028_userprofile_telefone'),
    ]

    operations = [
        migrations.AddField(
            model_name='comment',
            name='origem',
            field=models.CharField(
                choices=[('usuario', 'Usuário'), ('sistema', 'Sistema')],
                db_index=True,
                default='usuario',
                help_text='Comentário manual do usuário ou registro automático do sistema.',
                max_length=16,
                verbose_name='Origem',
            ),
        ),
        migrations.RunPython(forwards_classify_reprovacao_comments, migrations.RunPython.noop),
    ]
