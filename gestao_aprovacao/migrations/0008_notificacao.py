# Generated manually

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('gestao_aprovacao', '0007_userprofile'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notificacao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('pedido_criado', 'Novo Pedido Criado'), ('pedido_atualizado', 'Pedido Atualizado'), ('pedido_aprovado', 'Pedido Aprovado'), ('pedido_reprovado', 'Pedido Reprovado'), ('anexo_adicionado', 'Novo Anexo Adicionado'), ('comentario_adicionado', 'Novo Comentário')], max_length=50, verbose_name='Tipo de Notificação')),
                ('titulo', models.CharField(max_length=200, verbose_name='Título')),
                ('mensagem', models.TextField(verbose_name='Mensagem')),
                ('lida', models.BooleanField(default=False, verbose_name='Lida')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')),
                ('usuario', models.ForeignKey(help_text='Usuário que receberá a notificação', on_delete=django.db.models.deletion.CASCADE, related_name='notificacoes', to=settings.AUTH_USER_MODEL, verbose_name='Usuário')),
                ('work_order', models.ForeignKey(blank=True, help_text='Pedido relacionado à notificação (se aplicável)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notificacoes', to='gestao_aprovacao.workorder', verbose_name='Pedido Relacionado')),
            ],
            options={
                'verbose_name': 'Notificação',
                'verbose_name_plural': 'Notificações',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='notificacao',
            index=models.Index(fields=['usuario', 'lida', '-created_at'], name='obras_notif_usuario_idx'),
        ),
    ]

