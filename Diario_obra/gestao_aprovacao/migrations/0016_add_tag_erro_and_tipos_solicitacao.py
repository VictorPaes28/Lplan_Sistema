# Generated migration for TagErro model and Approval tags_erro field

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gestao_aprovacao', '0014_update_lembrete_tipos_recorrentes'),
    ]

    operations = [
        # Adicionar novos tipos de solicitação ao WorkOrder
        migrations.AlterField(
            model_name='workorder',
            name='tipo_solicitacao',
            field=models.CharField(
                choices=[
                    ('contrato', 'Contrato'),
                    ('medicao', 'Medição'),
                    ('ordem_servico', 'Ordem de Serviço (OS)'),
                    ('mapa_cotacao', 'Mapa de Cotação'),
                ],
                help_text='Tipo de solicitação: Contrato ou Medição',
                max_length=20,
                verbose_name='Tipo de Solicitação'
            ),
        ),
        
        # Criar modelo TagErro
        migrations.CreateModel(
            name='TagErro',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(help_text='Nome do motivo/tag de erro (ex: "Valor acima do orçamento", "Documentação incompleta")', max_length=200, verbose_name='Nome da Tag')),
                ('tipo_solicitacao', models.CharField(choices=[('contrato', 'Contrato'), ('medicao', 'Medição'), ('ordem_servico', 'Ordem de Serviço (OS)'), ('mapa_cotacao', 'Mapa de Cotação')], help_text='Tipo de solicitação ao qual esta tag se aplica', max_length=20, verbose_name='Tipo de Solicitação')),
                ('descricao', models.TextField(blank=True, help_text='Descrição detalhada do motivo de erro (opcional)', null=True, verbose_name='Descrição')),
                ('ativo', models.BooleanField(default=True, help_text='Indica se esta tag está ativa e disponível para seleção', verbose_name='Ativa')),
                ('ordem', models.IntegerField(default=0, help_text='Ordem de exibição (menor número aparece primeiro)', verbose_name='Ordem')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
            ],
            options={
                'verbose_name': 'Tag de Erro',
                'verbose_name_plural': 'Tags de Erro',
                'ordering': ['tipo_solicitacao', 'ordem', 'nome'],
                'unique_together': {('nome', 'tipo_solicitacao')},
            },
        ),
        
        # Adicionar campo tags_erro ao Approval (ManyToMany)
        migrations.AddField(
            model_name='approval',
            name='tags_erro',
            field=models.ManyToManyField(blank=True, help_text='Tags/motivos de erro selecionados para esta reprovação', related_name='approvals', to='gestao_aprovacao.tagerro', verbose_name='Tags de Erro'),
        ),
    ]

