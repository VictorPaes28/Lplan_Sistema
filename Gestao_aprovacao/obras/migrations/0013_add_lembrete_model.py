# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('obras', '0012_add_comment_model'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Lembrete',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dias_pendente', models.IntegerField(help_text='Quantos dias o pedido estava pendente quando o lembrete foi enviado', verbose_name='Dias Pendente')),
                ('enviado_em', models.DateTimeField(auto_now_add=True, help_text='Data/hora em que o lembrete foi enviado', verbose_name='Enviado Em')),
                ('tipo', models.CharField(choices=[('pendente_3_dias', 'Pendente há 3 dias'), ('pendente_5_dias', 'Pendente há 5 dias'), ('pendente_7_dias', 'Pendente há 7 dias'), ('pendente_10_dias', 'Pendente há 10 dias'), ('pendente_15_dias', 'Pendente há 15 dias')], help_text='Tipo de lembrete enviado', max_length=50, verbose_name='Tipo de Lembrete')),
                ('enviado_para', models.ForeignKey(help_text='Aprovador que recebeu o lembrete', on_delete=django.db.models.deletion.CASCADE, related_name='lembretes_recebidos', to='auth.user', verbose_name='Enviado Para')),
                ('work_order', models.ForeignKey(help_text='Pedido relacionado ao lembrete', on_delete=django.db.models.deletion.CASCADE, related_name='lembretes', to='obras.workorder', verbose_name='Pedido de Obra')),
            ],
            options={
                'verbose_name': 'Lembrete',
                'verbose_name_plural': 'Lembretes',
                'ordering': ['-enviado_em'],
            },
        ),
        migrations.AddIndex(
            model_name='lembrete',
            index=models.Index(fields=['work_order', 'enviado_para', 'enviado_em'], name='obras_lembr_work_or_idx'),
        ),
        migrations.AddIndex(
            model_name='lembrete',
            index=models.Index(fields=['enviado_para', 'enviado_em'], name='obras_lembr_enviado_idx'),
        ),
    ]

