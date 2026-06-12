from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0054_projectfront_description_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(
                choices=[
                    ('diary_pending', 'Relatório Pendente de Aprovação'),
                    ('diary_review', 'Relatório Requer Revisão'),
                    ('activity_delayed', 'Atividade Atrasada'),
                    ('system', 'Notificação do Sistema'),
                    ('rdo_pendente', 'RDO Aguardando Aprovação'),
                    ('rdo_aprovado', 'RDO Aprovado'),
                    ('rdo_reprovado', 'RDO Reprovado/Revisão'),
                    ('pedido_criado', 'Novo Pedido para Aprovar'),
                    ('pedido_reenviado', 'Pedido Reenviado para Aprovação'),
                    ('pedido_atualizado', 'Pedido Atualizado (Pendente)'),
                    ('pedido_aprovado', 'Pedido Aprovado'),
                    ('pedido_reprovado', 'Pedido Reprovado'),
                    ('pedido_comentario', 'Comentário em Pedido'),
                    ('pedido_exclusao_solicitada', 'Exclusão de Pedido Solicitada'),
                    ('pedido_exclusao_aprovada', 'Exclusão de Pedido Aprovada'),
                    ('pedido_exclusao_rejeitada', 'Exclusão de Pedido Rejeitada'),
                    ('restricao_criada', 'Nova Restrição Atribuída'),
                    ('restricao_status', 'Status de Restrição Alterado'),
                    ('restricao_prazo', 'Prazo de Restrição Vencendo'),
                    ('trackhub_etapa_concluida', 'Etapa Concluída no TrackHub'),
                    ('trackhub_prazo', 'Prazo de Etapa TrackHub'),
                    ('rh_requisicao_pendente', 'RH — Requisição para Aprovar'),
                    ('rh_requisicao_reprovada', 'RH — Requisição Reprovada'),
                    ('rh_coleta_docs', 'RH — Coleta de Documentos'),
                    ('rh_documento_recebido', 'RH — Documento Recebido'),
                    ('rh_documentacao_pronta', 'RH — Documentação Completa'),
                    ('rh_admissao_pendente', 'RH — Admissão Pendente'),
                    ('rh_documento_vencendo', 'RH — Documento Vencendo/Vencido'),
                ],
                max_length=50,
                verbose_name='Tipo de Notificação',
            ),
        ),
    ]
