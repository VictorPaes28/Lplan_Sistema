"""
Popula o GestControll com dados de teste usando obras e usuários já existentes.
Cria: tags de erro, pedidos (todos os status e tipos), comentários, aprovações,
histórico de status e notificações.

Uso:
    python manage.py seed_gestcontroll_dados
    python manage.py seed_gestcontroll_dados --limpar   # Remove apenas pedidos/comentários/aprovações/notificações antes
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from django.db.models import Max
from gestao_aprovacao.models import (
    Obra, WorkOrder, Approval, StatusHistory,
    WorkOrderPermission, Comment, Notificacao, TagErro,
)
from decimal import Decimal
from datetime import timedelta
import random


class Command(BaseCommand):
    help = 'Gera dados de teste para o GestControll (pedidos, comentários, aprovações, etc.) usando obras e usuários existentes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpar',
            action='store_true',
            help='Remove pedidos, comentários, aprovações, notificações e histórico antes de criar novos'
        )

    def handle(self, *args, **options):
        obras = list(Obra.objects.all().order_by('id'))
        if not obras:
            self.stdout.write(self.style.ERROR('Nenhuma obra encontrada. Crie obras no Painel ou no GestControll primeiro.'))
            return

        solicitantes, aprovadores = self._obter_solicitantes_e_aprovadores(obras)
        if not solicitantes or not aprovadores:
            self.stdout.write(
                self.style.WARNING(
                    'Solicitantes ou aprovadores insuficientes. '
                    'Vincule usuários às obras (Permissões por obra) ou crie usuários nos grupos Solicitante/Aprovador.'
                )
            )
            # Usa qualquer usuário ativo como fallback
            fallback = list(User.objects.filter(is_active=True)[:5])
            if not solicitantes and fallback:
                solicitantes = fallback[:2] if len(fallback) >= 2 else fallback
            if not aprovadores and fallback:
                aprovadores = [u for u in fallback if u not in solicitantes][:2] or fallback[:1]

        if not solicitantes or not aprovadores:
            self.stdout.write(self.style.ERROR('É necessário ter pelo menos 1 solicitante e 1 aprovador (ou usuários vinculados às obras).'))
            return

        if options['limpar']:
            self._limpar_dados()

        with transaction.atomic():
            self._criar_tags_erro()
            self._criar_pedidos_completos(obras, solicitantes, aprovadores)

        self.stdout.write(self.style.SUCCESS('\nDados do GestControll gerados com sucesso.'))

    def _obter_solicitantes_e_aprovadores(self, obras):
        """Obtém listas de usuários solicitantes e aprovadores a partir das permissões por obra."""
        ids_obras = [o.id for o in obras]
        perms = WorkOrderPermission.objects.filter(obra_id__in=ids_obras, ativo=True).select_related('usuario')
        solicitantes = list({p.usuario for p in perms if p.tipo_permissao == 'solicitante' and p.usuario.is_active})
        aprovadores = list({p.usuario for p in perms if p.tipo_permissao == 'aprovador' and p.usuario.is_active})
        if not solicitantes:
            from django.contrib.auth.models import Group
            g = Group.objects.filter(name='Solicitante').first()
            if g:
                solicitantes = list(g.user_set.filter(is_active=True)[:5])
        if not aprovadores:
            from django.contrib.auth.models import Group
            g = Group.objects.filter(name='Aprovador').first()
            if g:
                aprovadores = list(g.user_set.filter(is_active=True)[:5])
        return solicitantes, aprovadores

    def _limpar_dados(self):
        self.stdout.write('Limpando pedidos, comentários, aprovações, notificações e histórico...')
        Notificacao.objects.all().delete()
        Comment.objects.all().delete()
        Approval.objects.all().delete()
        StatusHistory.objects.all().delete()
        WorkOrder.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('   Dados limpos.'))

    def _proximo_codigo_obra(self, obra):
        """Retorna um código único para a obra (ex: PD-2025-001)."""
        ano = timezone.now().year
        existentes = WorkOrder.objects.filter(obra=obra).aggregate(Max('codigo'))
        max_cod = existentes.get('codigo__max')
        if max_cod and max_cod.startswith(f'PD-{ano}-'):
            try:
                seq = int(max_cod.split('-')[-1]) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        return f'PD-{ano}-{seq:03d}'

    def _criar_tags_erro(self):
        self.stdout.write('Criando tags de erro (se não existirem)...')
        tags_data = [
            ('Valor acima do orçamento', 'contrato', 'O valor do contrato excede o limite aprovado.', 1),
            ('Documentação incompleta', 'contrato', 'Faltam documentos obrigatórios para contratação.', 2),
            ('Fornecedor não homologado', 'contrato', 'O fornecedor não consta na lista de homologados.', 3),
            ('Medição acima do contratado', 'medicao', 'Valores medidos excedem o valor contratado.', 1),
            ('Falta ART/RRT', 'medicao', 'Não foi anexada a ART ou RRT do responsável técnico.', 2),
            ('OS sem justificativa técnica', 'ordem_servico', 'Falta justificativa técnica para a OS.', 1),
            ('Menos de 3 cotações', 'mapa_cotacao', 'É necessário no mínimo 3 cotações válidas.', 1),
            ('Cotações vencidas', 'mapa_cotacao', 'As cotações apresentadas estão fora do prazo de validade.', 2),
        ]
        for nome, tipo, desc, ordem in tags_data:
            TagErro.objects.get_or_create(
                nome=nome,
                tipo_solicitacao=tipo,
                defaults={'descricao': desc, 'ordem': ordem, 'ativo': True}
            )
        self.stdout.write(self.style.SUCCESS('   Tags de erro ok'))

    def _criar_pedidos_completos(self, obras, solicitantes, aprovadores):
        self.stdout.write('Criando pedidos com comentários, aprovações e notificações...')
        now = timezone.now()
        fornecedores = [
            'Concreteira Nacional S.A.', 'Ferragens & Aços Paulista', 'Madeireira Tropical LTDA',
            'Elétrica Raio LTDA', 'Hidráulica Master', 'Constru Material Express', 'Pedras & Revestimentos ABC',
            'Locação de Equipamentos Delta', 'Terraplanagem Norte', 'Impermeabiliza Tudo LTDA',
            'Pinturas & Acabamentos Premium', 'Elevadores Ascensão S.A.', 'Ar Condicionado Total',
        ]

        cenarios = [
            # Rascunhos
            {'status_final': 'rascunho', 'tipo': 'contrato', 'descricao': 'Contratação para instalações elétricas do bloco A', 'valor': Decimal('185000.00'), 'prazo': 45, 'dias_atras': 1},
            {'status_final': 'rascunho', 'tipo': 'mapa_cotacao', 'descricao': 'Cotação de porcelanato para áreas comuns - 3500m²', 'valor': Decimal('420000.00'), 'prazo': 30, 'dias_atras': 0},
            # Pendentes
            {'status_final': 'pendente', 'tipo': 'contrato', 'descricao': 'Contrato de impermeabilização das lajes da cobertura', 'valor': Decimal('95000.00'), 'prazo': 20, 'dias_atras': 3},
            {'status_final': 'pendente', 'tipo': 'medicao', 'descricao': '4ª Medição de fundação - Estacas hélice contínua', 'valor': Decimal('320000.00'), 'prazo': 5, 'dias_atras': 2},
            {'status_final': 'pendente', 'tipo': 'ordem_servico', 'descricao': 'OS para regularização de alvenaria no pavimento tipo 8', 'valor': Decimal('12500.00'), 'prazo': 7, 'dias_atras': 1},
            {'status_final': 'pendente', 'tipo': 'mapa_cotacao', 'descricao': 'Cotação para esquadrias de alumínio - 200 unidades', 'valor': Decimal('580000.00'), 'prazo': 60, 'dias_atras': 5},
            {'status_final': 'pendente', 'tipo': 'contrato', 'descricao': 'Contratação de mão de obra para alvenaria estrutural', 'valor': Decimal('230000.00'), 'prazo': 90, 'dias_atras': 7},
            # Aprovados
            {'status_final': 'aprovado', 'tipo': 'contrato', 'descricao': 'Contrato de locação de grua torre para fase estrutural', 'valor': Decimal('450000.00'), 'prazo': 180, 'dias_atras': 30},
            {'status_final': 'aprovado', 'tipo': 'medicao', 'descricao': '2ª Medição de estrutura - Formas e concretagem', 'valor': Decimal('280000.00'), 'prazo': 5, 'dias_atras': 20},
            {'status_final': 'aprovado', 'tipo': 'ordem_servico', 'descricao': 'OS para instalação de canteiro de obras', 'valor': Decimal('85000.00'), 'prazo': 15, 'dias_atras': 45},
            {'status_final': 'aprovado', 'tipo': 'mapa_cotacao', 'descricao': 'Cotação e compra de aço CA-50 e CA-60 - 120 toneladas', 'valor': Decimal('960000.00'), 'prazo': 30, 'dias_atras': 25},
            {'status_final': 'aprovado', 'tipo': 'contrato', 'descricao': 'Contratação de terraplanagem e preparo do terreno', 'valor': Decimal('175000.00'), 'prazo': 20, 'dias_atras': 60},
            {'status_final': 'aprovado', 'tipo': 'medicao', 'descricao': '1ª Medição de instalações hidráulicas - Água fria', 'valor': Decimal('67000.00'), 'prazo': 5, 'dias_atras': 15},
            # Reprovados
            {'status_final': 'reprovado', 'tipo': 'contrato', 'descricao': 'Contrato de pintura interna - áreas comuns e fachada', 'valor': Decimal('340000.00'), 'prazo': 60, 'dias_atras': 10},
            {'status_final': 'reprovado', 'tipo': 'mapa_cotacao', 'descricao': 'Cotação de elevadores - 4 unidades', 'valor': Decimal('1200000.00'), 'prazo': 120, 'dias_atras': 8},
            {'status_final': 'reprovado', 'tipo': 'medicao', 'descricao': '3ª Medição de alvenaria - Blocos cerâmicos', 'valor': Decimal('145000.00'), 'prazo': 5, 'dias_atras': 6},
            # Reaprovação
            {'status_final': 'reaprovacao', 'tipo': 'contrato', 'descricao': 'Contrato de instalações de SPDA e aterramento', 'valor': Decimal('78000.00'), 'prazo': 25, 'dias_atras': 12},
            {'status_final': 'reaprovacao', 'tipo': 'mapa_cotacao', 'descricao': 'Cotação de louças e metais sanitários - 180 aptos', 'valor': Decimal('390000.00'), 'prazo': 45, 'dias_atras': 9},
            # Cancelados
            {'status_final': 'cancelado', 'tipo': 'ordem_servico', 'descricao': 'OS para demolição de muro (cancelada - muro preservado)', 'valor': Decimal('15000.00'), 'prazo': 5, 'dias_atras': 40},
            {'status_final': 'cancelado', 'tipo': 'contrato', 'descricao': 'Contrato de paisagismo (cancelado - escopo alterado)', 'valor': Decimal('95000.00'), 'prazo': 30, 'dias_atras': 35},
        ]

        total_pedidos = total_aprovacoes = total_comentarios = total_notificacoes = total_historico = 0

        for cenario in cenarios:
            obra = random.choice(obras)
            solicitante = random.choice(solicitantes)
            aprovador = random.choice(aprovadores)
            codigo = self._proximo_codigo_obra(obra)
            data_criacao = now - timedelta(days=cenario['dias_atras'])

            wo = WorkOrder(
                obra=obra,
                codigo=codigo,
                nome_credor=random.choice(fornecedores),
                tipo_solicitacao=cenario['tipo'],
                observacoes=cenario['descricao'],
                valor_estimado=cenario['valor'],
                prazo_estimado=cenario['prazo'],
                local=f'{obra.nome} - {random.choice(["Bloco A", "Bloco B", "Torre 1", "Subsolo", "Cobertura", "Térreo"])}',
                status='rascunho',
                criado_por=solicitante,
            )
            wo.save()
            total_pedidos += 1

            StatusHistory.objects.create(
                work_order=wo,
                status_anterior=None,
                status_novo='rascunho',
                alterado_por=solicitante,
                observacao='Pedido criado como rascunho',
            )
            total_historico += 1

            status_final = cenario['status_final']

            if status_final in ['pendente', 'aprovado', 'reprovado', 'reaprovacao', 'cancelado']:
                if status_final != 'cancelado' or random.random() > 0.5:
                    wo.status = 'pendente'
                    wo.data_envio = data_criacao + timedelta(hours=random.randint(1, 48))
                    wo.save()
                    StatusHistory.objects.create(
                        work_order=wo,
                        status_anterior='rascunho',
                        status_novo='pendente',
                        alterado_por=solicitante,
                        observacao='Pedido enviado para aprovação',
                    )
                    total_historico += 1
                    for aprov in aprovadores:
                        Notificacao.objects.create(
                            usuario=aprov,
                            tipo='pedido_criado',
                            titulo=f'Novo pedido: {codigo}',
                            mensagem=f'O pedido {codigo} ({cenario["tipo"]}) foi enviado para aprovação por {solicitante.get_full_name() or solicitante.username}.',
                            work_order=wo,
                            lida=random.choice([True, True, False]),
                        )
                        total_notificacoes += 1

            if status_final == 'aprovado':
                wo.status = 'aprovado'
                wo.data_aprovacao = (wo.data_envio or wo.created_at) + timedelta(hours=random.randint(2, 72))
                wo.save()
                Approval.objects.create(
                    work_order=wo,
                    aprovado_por=aprovador,
                    decisao='aprovado',
                    comentario=random.choice([
                        'Documentação conforme. Aprovado.',
                        'Valores dentro do orçamento previsto. Pode prosseguir.',
                        'OK. Verificado junto à equipe de engenharia.',
                        'Aprovado conforme alinhamento em reunião.',
                    ]),
                )
                total_aprovacoes += 1
                StatusHistory.objects.create(
                    work_order=wo,
                    status_anterior='pendente',
                    status_novo='aprovado',
                    alterado_por=aprovador,
                    observacao=f'Aprovado por {aprovador.get_full_name() or aprovador.username}',
                )
                total_historico += 1
                Notificacao.objects.create(
                    usuario=solicitante,
                    tipo='pedido_aprovado',
                    titulo=f'Pedido {codigo} aprovado!',
                    mensagem=f'Seu pedido {codigo} foi aprovado por {aprovador.get_full_name() or aprovador.username}.',
                    work_order=wo,
                    lida=random.choice([True, False]),
                )
                total_notificacoes += 1

            elif status_final in ['reprovado', 'reaprovacao']:
                wo.status = 'reprovado'
                wo.data_aprovacao = (wo.data_envio or wo.created_at) + timedelta(hours=random.randint(4, 48))
                wo.save()
                comentarios_reprov = [
                    'Documentação incompleta. Favor revisar e reenviar.',
                    'Valores acima do limite aprovado para esta fase.',
                    'Necessário incluir mais cotações para análise.',
                    'Especificações técnicas precisam ser revisadas.',
                ]
                approval = Approval.objects.create(
                    work_order=wo,
                    aprovado_por=aprovador,
                    decisao='reprovado',
                    comentario=random.choice(comentarios_reprov),
                )
                total_aprovacoes += 1
                tags_disponiveis = list(TagErro.objects.filter(tipo_solicitacao=cenario['tipo'], ativo=True))
                if tags_disponiveis:
                    approval.tags_erro.set(random.sample(tags_disponiveis, min(random.randint(1, 2), len(tags_disponiveis))))
                StatusHistory.objects.create(
                    work_order=wo,
                    status_anterior='pendente',
                    status_novo='reprovado',
                    alterado_por=aprovador,
                    observacao=f'Reprovado por {aprovador.get_full_name() or aprovador.username}',
                )
                total_historico += 1
                Notificacao.objects.create(
                    usuario=solicitante,
                    tipo='pedido_reprovado',
                    titulo=f'Pedido {codigo} reprovado',
                    mensagem=f'Seu pedido {codigo} foi reprovado. Verifique os motivos.',
                    work_order=wo,
                    lida=False,
                )
                total_notificacoes += 1

                if status_final == 'reaprovacao':
                    wo.status = 'reaprovacao'
                    wo.save()
                    StatusHistory.objects.create(
                        work_order=wo,
                        status_anterior='reprovado',
                        status_novo='reaprovacao',
                        alterado_por=solicitante,
                        observacao='Documentação corrigida e reenviada para aprovação',
                    )
                    total_historico += 1
                    Comment.objects.create(
                        work_order=wo,
                        autor=solicitante,
                        texto='Corrigi os pontos apontados na reprovação. Por favor, reavaliar.',
                    )
                    total_comentarios += 1

            elif status_final == 'cancelado':
                status_ant = wo.status
                wo.status = 'cancelado'
                wo.save()
                StatusHistory.objects.create(
                    work_order=wo,
                    status_anterior=status_ant,
                    status_novo='cancelado',
                    alterado_por=solicitante,
                    observacao=random.choice([
                        'Escopo do projeto foi alterado. Serviço não é mais necessário.',
                        'Obra paralisada temporariamente por decisão da diretoria.',
                    ]),
                )
                total_historico += 1

            if status_final != 'rascunho' and random.random() > 0.35:
                comentarios_genericos = [
                    ('Preciso desse pedido com urgência para não atrasar o cronograma.', solicitante),
                    ('Favor verificar se o valor inclui BDI.', aprovador),
                    ('A equipe de campo já está aguardando essa definição.', solicitante),
                    ('Vou analisar com atenção e retorno em breve.', aprovador),
                    ('Segue em anexo o memorial descritivo atualizado.', solicitante),
                ]
                for _ in range(random.randint(1, 3)):
                    texto, autor = random.choice(comentarios_genericos)
                    Comment.objects.create(work_order=wo, autor=autor, texto=texto)
                    total_comentarios += 1

        self.stdout.write(self.style.SUCCESS(f'   {total_pedidos} pedidos'))
        self.stdout.write(self.style.SUCCESS(f'   {total_aprovacoes} aprovações/reprovações'))
        self.stdout.write(self.style.SUCCESS(f'   {total_comentarios} comentários'))
        self.stdout.write(self.style.SUCCESS(f'   {total_notificacoes} notificações'))
        self.stdout.write(self.style.SUCCESS(f'   {total_historico} registros de histórico'))
