# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('obras', '0011_add_motivo_exclusao'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('texto', models.TextField(help_text='Texto do comentário', verbose_name='Comentário')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Data/Hora do Comentário')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Data/Hora da Última Atualização')),
                ('autor', models.ForeignKey(help_text='Usuário que fez o comentário', on_delete=django.db.models.deletion.PROTECT, related_name='comentarios_feitos', to='auth.user', verbose_name='Autor')),
                ('work_order', models.ForeignKey(help_text='Pedido de obra relacionado', on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='obras.workorder', verbose_name='Pedido de Obra')),
            ],
            options={
                'verbose_name': 'Comentário',
                'verbose_name_plural': 'Comentários',
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='comment',
            index=models.Index(fields=['work_order', 'created_at'], name='obras_commen_work_or_idx'),
        ),
        migrations.AddIndex(
            model_name='comment',
            index=models.Index(fields=['autor', 'created_at'], name='obras_commen_autor_i_idx'),
        ),
    ]

