# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('obras', '0009_add_versao_reaprovacao'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.AddField(
            model_name='workorder',
            name='solicitado_exclusao',
            field=models.BooleanField(default=False, help_text='Indica se o pedido foi solicitado para exclusão pelo solicitante', verbose_name='Solicitado para Exclusão'),
        ),
        migrations.AddField(
            model_name='workorder',
            name='solicitado_exclusao_em',
            field=models.DateTimeField(blank=True, help_text='Data e hora em que a exclusão foi solicitada', null=True, verbose_name='Solicitado Exclusão Em'),
        ),
        migrations.AddField(
            model_name='workorder',
            name='solicitado_exclusao_por',
            field=models.ForeignKey(blank=True, help_text='Usuário que solicitou a exclusão do pedido', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pedidos_solicitados_exclusao', to='auth.user', verbose_name='Solicitado Exclusão Por'),
        ),
        migrations.AlterField(
            model_name='notificacao',
            name='tipo',
            field=models.CharField(choices=[('pedido_criado', 'Novo Pedido Criado'), ('pedido_atualizado', 'Pedido Atualizado'), ('pedido_aprovado', 'Pedido Aprovado'), ('pedido_reprovado', 'Pedido Reprovado'), ('anexo_adicionado', 'Novo Anexo Adicionado'), ('anexo_removido', 'Anexo Removido'), ('comentario_adicionado', 'Novo Comentário'), ('exclusao_solicitada', 'Exclusão Solicitada'), ('exclusao_aprovada', 'Exclusão Aprovada'), ('exclusao_rejeitada', 'Exclusão Rejeitada')], max_length=50, verbose_name='Tipo de Notificação'),
        ),
    ]

