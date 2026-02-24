"""
Comando para popular o banco com dados de teste para o GestControll.
Cria empresas, obras, usuários, pedidos com diversos status, aprovações,
comentários, notificações, tags de erro e permissões.

Uso:
    python manage.py seed_gestcontroll              # Cria dados padrão
    python manage.py seed_gestcontroll --limpar     # Limpa e recria tudo
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.db import transaction
from django.utils import timezone
from gestao_aprovacao.models import (
    Empresa, Obra, WorkOrder, Approval, Attachment, StatusHistory,
    WorkOrderPermission, UserEmpresa, Comment, Notificacao, TagErro, EmailLog
)
from decimal import Decimal
from datetime import timedelta
import random


class Command(BaseCommand):
    help = 'Popula o banco com dados de teste realistas para o GestControll'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpar',
            action='store_true',
            help='Limpa dados existentes antes de criar novos'
        )

    def handle(self, *args, **options):
        if options['limpar']:
            self.stdout.write('Limpando dados existentes do GestControll...')
            EmailLog.objects.all().delete()
            Notificacao.objects.all().delete()
            Comment.objects.all().delete()
            Approval.objects.all().delete()
            Attachment.objects.all().delete()
            StatusHistory.objects.all().delete()
            WorkOrderPermission.objects.all().delete()
            WorkOrder.objects.all().delete()
            UserEmpresa.objects.all().delete()
            Obra.objects.filter(empresa__isnull=False).delete()
            Empresa.objects.all().delete()
            TagErro.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('   Dados do GestControll limpos!'))

        with transaction.atomic():
            self.criar_grupos()
            usuarios = self.criar_usuarios()
            empresas = self.criar_empresas(usuarios)
            obras = self.criar_obras(empresas)
            self.criar_vinculos(usuarios, empresas, obras)
            self.criar_tags_erro()
            self.criar_pedidos(usuarios, obras)

        self.stdout.write(self.style.SUCCESS('\nSeed GestControll concluido! Sistema pronto para testes.'))
        self.stdout.write('\nUsuarios de teste:')
        self.stdout.write('   admin / admin123 (Administrador - superuser)')
        self.stdout.write('   gestor.carlos / gestor123 (Responsavel Empresa)')
        self.stdout.write('   gestor.ana / gestor123 (Responsavel Empresa)')
        self.stdout.write('   aprovador.marcos / aprov123 (Aprovador)')
        self.stdout.write('   aprovador.julia / aprov123 (Aprovador)')
        self.stdout.write('   eng.ricardo / eng123 (Solicitante)')
        self.stdout.write('   eng.fernanda / eng123 (Solicitante)')
        self.stdout.write('   eng.lucas / eng123 (Solicitante)')

    # ────────────────────────────────────────────────
    # GRUPOS
    # ────────────────────────────────────────────────
    def criar_grupos(self):
        self.stdout.write('Criando grupos...')
        for nome in ['Administrador', 'Responsavel Empresa', 'Aprovador', 'Solicitante']:
            Group.objects.get_or_create(name=nome)
        self.stdout.write(self.style.SUCCESS('   Grupos criados/verificados'))

    # ────────────────────────────────────────────────
    # USUARIOS
    # ────────────────────────────────────────────────
    def criar_usuarios(self):
        self.stdout.write('Criando usuarios de teste...')
        usuarios = {}

        # Admin / Superuser
        u, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'first_name': 'Administrador',
                'last_name': 'Sistema',
                'email': 'admin@lplan.com.br',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            u.set_password('admin123')
            u.save()
        u.groups.add(Group.objects.get(name='Administrador'))
        usuarios['admin'] = u

        # Gestores (Responsavel Empresa)
        gestores_data = [
            ('gestor.carlos', 'Carlos', 'Mendonça', 'carlos.mendonca@lplan.com.br'),
            ('gestor.ana', 'Ana', 'Beatriz Silva', 'ana.silva@lplan.com.br'),
        ]
        for username, first, last, email in gestores_data:
            u, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'email': email,
                    'is_staff': False,
                }
            )
            if created:
                u.set_password('gestor123')
                u.save()
            u.groups.add(Group.objects.get(name='Responsavel Empresa'))
            usuarios[username] = u

        # Aprovadores
        aprovadores_data = [
            ('aprovador.marcos', 'Marcos', 'Oliveira', 'marcos.oliveira@lplan.com.br'),
            ('aprovador.julia', 'Júlia', 'Costa', 'julia.costa@lplan.com.br'),
        ]
        for username, first, last, email in aprovadores_data:
            u, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'email': email,
                    'is_staff': False,
                }
            )
            if created:
                u.set_password('aprov123')
                u.save()
            u.groups.add(Group.objects.get(name='Aprovador'))
            usuarios[username] = u

        # Solicitantes (Engenheiros)
        solicitantes_data = [
            ('eng.ricardo', 'Ricardo', 'Almeida', 'ricardo.almeida@lplan.com.br'),
            ('eng.fernanda', 'Fernanda', 'Rodrigues', 'fernanda.rodrigues@lplan.com.br'),
            ('eng.lucas', 'Lucas', 'Pereira', 'lucas.pereira@lplan.com.br'),
        ]
        for username, first, last, email in solicitantes_data:
            u, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'email': email,
                    'is_staff': False,
                }
            )
            if created:
                u.set_password('eng123')
                u.save()
            u.groups.add(Group.objects.get(name='Solicitante'))
            usuarios[username] = u

        self.stdout.write(self.style.SUCCESS(f'   {len(usuarios)} usuarios criados/verificados'))
        return usuarios

    # ────────────────────────────────────────────────
    # EMPRESAS
    # ────────────────────────────────────────────────
    def criar_empresas(self, usuarios):
        self.stdout.write('Criando empresas...')
        empresas = []

        empresas_data = [
            {
                'codigo': 'EMP-001',
                'nome': 'Construtora Horizonte LTDA',
                'email': 'contato@horizonte.com.br',
                'telefone': '(11) 3456-7890',
                'responsavel': usuarios.get('gestor.carlos'),
            },
            {
                'codigo': 'EMP-002',
                'nome': 'Engenharia Vértice S.A.',
                'email': 'contato@vertice.eng.br',
                'telefone': '(21) 2345-6789',
                'responsavel': usuarios.get('gestor.ana'),
            },
            {
                'codigo': 'EMP-003',
                'nome': 'MegaObras Incorporação',
                'email': 'obras@megaobras.com.br',
                'telefone': '(31) 3333-4444',
                'responsavel': None,
            },
        ]

        for data in empresas_data:
            emp, _ = Empresa.objects.get_or_create(
                codigo=data['codigo'],
                defaults=data
            )
            empresas.append(emp)
            self.stdout.write(f'   {emp.codigo} - {emp.nome}')

        self.stdout.write(self.style.SUCCESS(f'   {len(empresas)} empresas criadas'))
        return empresas

    # ────────────────────────────────────────────────
    # OBRAS
    # ────────────────────────────────────────────────
    def criar_obras(self, empresas):
        self.stdout.write('Criando obras...')
        obras = []

        obras_data = [
            # Empresa 1 - Horizonte
            {
                'empresa': empresas[0],
                'codigo': 'OBR-101',
                'nome': 'Residencial Vista Mar - Torre A',
                'descricao': 'Edifício residencial de alto padrão com 25 pavimentos, localizado na orla de Santos/SP.',
                'email_obra': 'vistamar@horizonte.com.br',
            },
            {
                'empresa': empresas[0],
                'codigo': 'OBR-102',
                'nome': 'Condomínio Parque Verde',
                'descricao': 'Condomínio horizontal com 120 unidades em Campinas/SP. Infraestrutura completa.',
                'email_obra': 'parqueverde@horizonte.com.br',
            },
            {
                'empresa': empresas[0],
                'codigo': 'OBR-103',
                'nome': 'Centro Comercial Ipiranga',
                'descricao': 'Shopping center com 3 pisos, 85 lojas e estacionamento para 400 veículos.',
                'email_obra': 'ipiranga@horizonte.com.br',
            },
            # Empresa 2 - Vértice
            {
                'empresa': empresas[1],
                'codigo': 'OBR-201',
                'nome': 'Edifício Corporate Tower',
                'descricao': 'Escritórios de alto padrão no centro do Rio de Janeiro. 30 andares com lajes corporativas.',
                'email_obra': 'corporate@vertice.eng.br',
            },
            {
                'empresa': empresas[1],
                'codigo': 'OBR-202',
                'nome': 'Hospital Regional Sudeste',
                'descricao': 'Construção de hospital com 200 leitos, centro cirúrgico e UTI.',
                'email_obra': 'hospital@vertice.eng.br',
            },
            # Empresa 3 - MegaObras
            {
                'empresa': empresas[2],
                'codigo': 'OBR-301',
                'nome': 'Galpão Logístico Contagem',
                'descricao': 'Galpão logístico de 15.000m² em Contagem/MG com docas e pé-direito de 12m.',
                'email_obra': 'logistica@megaobras.com.br',
            },
        ]

        for data in obras_data:
            obra, _ = Obra.objects.get_or_create(
                empresa=data['empresa'],
                codigo=data['codigo'],
                defaults={
                    'nome': data['nome'],
                    'descricao': data['descricao'],
                    'email_obra': data['email_obra'],
                    'ativo': True,
                }
            )
            obras.append(obra)
            self.stdout.write(f'   {obra.codigo} - {obra.nome}')

        self.stdout.write(self.style.SUCCESS(f'   {len(obras)} obras criadas'))
        return obras

    # ────────────────────────────────────────────────
    # VINCULOS USUARIO-EMPRESA E PERMISSOES POR OBRA
    # ────────────────────────────────────────────────
    def criar_vinculos(self, usuarios, empresas, obras):
        self.stdout.write('Criando vinculos e permissoes...')

        # Vincular gestores às suas empresas
        UserEmpresa.objects.get_or_create(usuario=usuarios['gestor.carlos'], empresa=empresas[0])
        UserEmpresa.objects.get_or_create(usuario=usuarios['gestor.ana'], empresa=empresas[1])

        # Vincular solicitantes a empresas
        UserEmpresa.objects.get_or_create(usuario=usuarios['eng.ricardo'], empresa=empresas[0])
        UserEmpresa.objects.get_or_create(usuario=usuarios['eng.fernanda'], empresa=empresas[0])
        UserEmpresa.objects.get_or_create(usuario=usuarios['eng.fernanda'], empresa=empresas[1])
        UserEmpresa.objects.get_or_create(usuario=usuarios['eng.lucas'], empresa=empresas[1])
        UserEmpresa.objects.get_or_create(usuario=usuarios['eng.lucas'], empresa=empresas[2])

        # Vincular aprovadores a empresas
        UserEmpresa.objects.get_or_create(usuario=usuarios['aprovador.marcos'], empresa=empresas[0])
        UserEmpresa.objects.get_or_create(usuario=usuarios['aprovador.marcos'], empresa=empresas[1])
        UserEmpresa.objects.get_or_create(usuario=usuarios['aprovador.julia'], empresa=empresas[1])
        UserEmpresa.objects.get_or_create(usuario=usuarios['aprovador.julia'], empresa=empresas[2])

        # Permissoes por obra
        # Obras Horizonte (0, 1, 2)
        for obra in obras[:3]:
            WorkOrderPermission.objects.get_or_create(
                obra=obra, usuario=usuarios['eng.ricardo'], tipo_permissao='solicitante'
            )
            WorkOrderPermission.objects.get_or_create(
                obra=obra, usuario=usuarios['eng.fernanda'], tipo_permissao='solicitante'
            )
            WorkOrderPermission.objects.get_or_create(
                obra=obra, usuario=usuarios['aprovador.marcos'], tipo_permissao='aprovador'
            )

        # Obras Vértice (3, 4)
        for obra in obras[3:5]:
            WorkOrderPermission.objects.get_or_create(
                obra=obra, usuario=usuarios['eng.fernanda'], tipo_permissao='solicitante'
            )
            WorkOrderPermission.objects.get_or_create(
                obra=obra, usuario=usuarios['eng.lucas'], tipo_permissao='solicitante'
            )
            WorkOrderPermission.objects.get_or_create(
                obra=obra, usuario=usuarios['aprovador.marcos'], tipo_permissao='aprovador'
            )
            WorkOrderPermission.objects.get_or_create(
                obra=obra, usuario=usuarios['aprovador.julia'], tipo_permissao='aprovador'
            )

        # Obras MegaObras (5)
        WorkOrderPermission.objects.get_or_create(
            obra=obras[5], usuario=usuarios['eng.lucas'], tipo_permissao='solicitante'
        )
        WorkOrderPermission.objects.get_or_create(
            obra=obras[5], usuario=usuarios['aprovador.julia'], tipo_permissao='aprovador'
        )

        self.stdout.write(self.style.SUCCESS('   Vinculos e permissoes criados'))

    # ────────────────────────────────────────────────
    # TAGS DE ERRO
    # ────────────────────────────────────────────────
    def criar_tags_erro(self):
        self.stdout.write('Criando tags de erro...')
        tags_data = [
            # Contratos
            ('Valor acima do orçamento', 'contrato', 'O valor do contrato excede o limite aprovado.', 1),
            ('Documentação incompleta', 'contrato', 'Faltam documentos obrigatórios para contratação.', 2),
            ('Fornecedor não homologado', 'contrato', 'O fornecedor não consta na lista de homologados.', 3),
            ('Escopo divergente', 'contrato', 'O escopo do contrato diverge do memorial descritivo.', 4),
            ('Prazo inadequado', 'contrato', 'O prazo proposto é incompatível com o cronograma.', 5),
            # Medições
            ('Medição acima do contratado', 'medicao', 'Valores medidos excedem o valor contratado.', 1),
            ('Falta ART/RRT', 'medicao', 'Não foi anexada a ART ou RRT do responsável técnico.', 2),
            ('Fotos insuficientes', 'medicao', 'Registro fotográfico insuficiente para comprovação.', 3),
            ('Boletim de medição incorreto', 'medicao', 'Erros nos cálculos do boletim de medição.', 4),
            # Ordem de Serviço
            ('OS sem justificativa técnica', 'ordem_servico', 'Falta justificativa técnica para a OS.', 1),
            ('Local de execução incorreto', 'ordem_servico', 'Localização da execução está incorreta.', 2),
            ('Conflito com outra OS', 'ordem_servico', 'Existe outra OS ativa para o mesmo serviço.', 3),
            # Mapa de Cotação
            ('Menos de 3 cotações', 'mapa_cotacao', 'É necessário no mínimo 3 cotações válidas.', 1),
            ('Cotações vencidas', 'mapa_cotacao', 'As cotações apresentadas estão fora do prazo de validade.', 2),
            ('Comparativo incompleto', 'mapa_cotacao', 'O quadro comparativo não está completo.', 3),
            ('Especificação divergente', 'mapa_cotacao', 'Especificações dos materiais divergem entre cotações.', 4),
        ]

        count = 0
        for nome, tipo, desc, ordem in tags_data:
            _, created = TagErro.objects.get_or_create(
                nome=nome,
                tipo_solicitacao=tipo,
                defaults={'descricao': desc, 'ordem': ordem, 'ativo': True}
            )
            if created:
                count += 1

        self.stdout.write(self.style.SUCCESS(f'   {count} tags de erro criadas'))

    # ────────────────────────────────────────────────
    # PEDIDOS (WorkOrders) COM HISTORICO COMPLETO
    # ────────────────────────────────────────────────
    def criar_pedidos(self, usuarios, obras):
        self.stdout.write('Criando pedidos de obra...')

        now = timezone.now()
        solicitantes = [usuarios['eng.ricardo'], usuarios['eng.fernanda'], usuarios['eng.lucas']]
        aprovadores = [usuarios['aprovador.marcos'], usuarios['aprovador.julia']]

        # Fornecedores realistas
        fornecedores = [
            'Concreteira Nacional S.A.',
            'Ferragens & Aços Paulista',
            'Madeireira Tropical LTDA',
            'Elétrica Raio LTDA',
            'Hidráulica Master',
            'Constru Material Express',
            'Pedras & Revestimentos ABC',
            'Locação de Equipamentos Delta',
            'Terraplanagem Norte',
            'Impermeabiliza Tudo LTDA',
            'Vidraçaria Transparente',
            'Pinturas & Acabamentos Premium',
            'Elevadores Ascensão S.A.',
            'Ar Condicionado Total',
            'Segurança do Trabalho Brasil',
        ]

        # Definições de pedidos com cenários realistas
        pedidos_cenarios = [
            # ── RASCUNHOS (2) ──
            {
                'status_final': 'rascunho',
                'tipo': 'contrato',
                'descricao': 'Contratação de empresa para instalações elétricas do bloco A',
                'valor': Decimal('185000.00'),
                'prazo': 45,
                'dias_atras': 1,
            },
            {
                'status_final': 'rascunho',
                'tipo': 'mapa_cotacao',
                'descricao': 'Cotação de porcelanato para áreas comuns - 3500m²',
                'valor': Decimal('420000.00'),
                'prazo': 30,
                'dias_atras': 0,
            },

            # ── PENDENTES (5) ──
            {
                'status_final': 'pendente',
                'tipo': 'contrato',
                'descricao': 'Contrato de impermeabilização das lajes da cobertura',
                'valor': Decimal('95000.00'),
                'prazo': 20,
                'dias_atras': 3,
            },
            {
                'status_final': 'pendente',
                'tipo': 'medicao',
                'descricao': '4ª Medição de fundação - Estacas hélice contínua',
                'valor': Decimal('320000.00'),
                'prazo': 5,
                'dias_atras': 2,
            },
            {
                'status_final': 'pendente',
                'tipo': 'ordem_servico',
                'descricao': 'OS para regularização de alvenaria no pavimento tipo 8',
                'valor': Decimal('12500.00'),
                'prazo': 7,
                'dias_atras': 1,
            },
            {
                'status_final': 'pendente',
                'tipo': 'mapa_cotacao',
                'descricao': 'Cotação para esquadrias de alumínio - 200 unidades',
                'valor': Decimal('580000.00'),
                'prazo': 60,
                'dias_atras': 5,
            },
            {
                'status_final': 'pendente',
                'tipo': 'contrato',
                'descricao': 'Contratação de mão de obra para alvenaria estrutural',
                'valor': Decimal('230000.00'),
                'prazo': 90,
                'dias_atras': 7,
            },

            # ── APROVADOS (6) ──
            {
                'status_final': 'aprovado',
                'tipo': 'contrato',
                'descricao': 'Contrato de locação de grua torre para fase estrutural',
                'valor': Decimal('450000.00'),
                'prazo': 180,
                'dias_atras': 30,
            },
            {
                'status_final': 'aprovado',
                'tipo': 'medicao',
                'descricao': '2ª Medição de estrutura - Formas e concretagem',
                'valor': Decimal('280000.00'),
                'prazo': 5,
                'dias_atras': 20,
            },
            {
                'status_final': 'aprovado',
                'tipo': 'ordem_servico',
                'descricao': 'OS para instalação de canteiro de obras',
                'valor': Decimal('85000.00'),
                'prazo': 15,
                'dias_atras': 45,
            },
            {
                'status_final': 'aprovado',
                'tipo': 'mapa_cotacao',
                'descricao': 'Cotação e compra de aço CA-50 e CA-60 - 120 toneladas',
                'valor': Decimal('960000.00'),
                'prazo': 30,
                'dias_atras': 25,
            },
            {
                'status_final': 'aprovado',
                'tipo': 'contrato',
                'descricao': 'Contratação de terraplanagem e preparo do terreno',
                'valor': Decimal('175000.00'),
                'prazo': 20,
                'dias_atras': 60,
            },
            {
                'status_final': 'aprovado',
                'tipo': 'medicao',
                'descricao': '1ª Medição de instalações hidráulicas - Água fria',
                'valor': Decimal('67000.00'),
                'prazo': 5,
                'dias_atras': 15,
            },

            # ── REPROVADOS (3) ──
            {
                'status_final': 'reprovado',
                'tipo': 'contrato',
                'descricao': 'Contrato de pintura interna - áreas comuns e fachada',
                'valor': Decimal('340000.00'),
                'prazo': 60,
                'dias_atras': 10,
            },
            {
                'status_final': 'reprovado',
                'tipo': 'mapa_cotacao',
                'descricao': 'Cotação de elevadores - 4 unidades',
                'valor': Decimal('1200000.00'),
                'prazo': 120,
                'dias_atras': 8,
            },
            {
                'status_final': 'reprovado',
                'tipo': 'medicao',
                'descricao': '3ª Medição de alvenaria - Blocos cerâmicos',
                'valor': Decimal('145000.00'),
                'prazo': 5,
                'dias_atras': 6,
            },

            # ── REAPROVAÇÃO (2) ──
            {
                'status_final': 'reaprovacao',
                'tipo': 'contrato',
                'descricao': 'Contrato de instalações de SPDA e aterramento',
                'valor': Decimal('78000.00'),
                'prazo': 25,
                'dias_atras': 12,
            },
            {
                'status_final': 'reaprovacao',
                'tipo': 'mapa_cotacao',
                'descricao': 'Cotação de louças e metais sanitários - 180 aptos',
                'valor': Decimal('390000.00'),
                'prazo': 45,
                'dias_atras': 9,
            },

            # ── CANCELADOS (2) ──
            {
                'status_final': 'cancelado',
                'tipo': 'ordem_servico',
                'descricao': 'OS para demolição de muro existente (cancelada - muro preservado)',
                'valor': Decimal('15000.00'),
                'prazo': 5,
                'dias_atras': 40,
            },
            {
                'status_final': 'cancelado',
                'tipo': 'contrato',
                'descricao': 'Contrato de paisagismo (cancelado - escopo alterado)',
                'valor': Decimal('95000.00'),
                'prazo': 30,
                'dias_atras': 35,
            },
        ]

        total_pedidos = 0
        total_aprovacoes = 0
        total_comentarios = 0
        total_notificacoes = 0
        total_historico = 0

        for i, cenario in enumerate(pedidos_cenarios):
            obra = random.choice(obras)
            solicitante = random.choice(solicitantes)
            aprovador = random.choice(aprovadores)
            fornecedor = random.choice(fornecedores)

            codigo = f'PD-{now.year}-{str(i + 1).zfill(3)}'
            data_criacao = now - timedelta(days=cenario['dias_atras'])

            # Verificar se já existe
            if WorkOrder.objects.filter(obra=obra, codigo=codigo).exists():
                continue

            # Criar pedido (inicia como rascunho)
            wo = WorkOrder(
                obra=obra,
                codigo=codigo,
                nome_credor=fornecedor,
                tipo_solicitacao=cenario['tipo'],
                observacoes=cenario['descricao'],
                valor_estimado=cenario['valor'],
                prazo_estimado=cenario['prazo'],
                local=f'{obra.nome} - {random.choice(["Bloco A", "Bloco B", "Torre 1", "Subsolo", "Cobertura", "Térreo", "Pavimento Tipo"])}',
                status='rascunho',
                criado_por=solicitante,
            )
            wo.save()
            total_pedidos += 1

            # Historico: criação
            StatusHistory.objects.create(
                work_order=wo,
                status_anterior=None,
                status_novo='rascunho',
                alterado_por=solicitante,
                observacao='Pedido criado como rascunho',
            )
            total_historico += 1

            status_final = cenario['status_final']

            # ── Transição: rascunho → pendente ──
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

                    # Notificação para aprovadores
                    for aprov in aprovadores:
                        Notificacao.objects.create(
                            usuario=aprov,
                            tipo='pedido_criado',
                            titulo=f'Novo pedido: {codigo}',
                            mensagem=f'O pedido {codigo} ({cenario["tipo"]}) foi enviado para aprovação por {solicitante.get_full_name()}.',
                            work_order=wo,
                            lida=random.choice([True, True, False]),
                        )
                        total_notificacoes += 1

            # ── Transição: pendente → aprovado ──
            if status_final == 'aprovado':
                wo.status = 'aprovado'
                wo.data_aprovacao = wo.data_envio + timedelta(hours=random.randint(2, 72))
                wo.save()

                comentarios_aprovacao = [
                    'Documentação conforme. Aprovado.',
                    'Valores dentro do orçamento previsto. Pode prosseguir.',
                    'OK. Verificado junto à equipe de engenharia.',
                    'Aprovado conforme alinhamento em reunião.',
                    'Tudo certo. Encaminhar para contratação.',
                ]
                approval = Approval.objects.create(
                    work_order=wo,
                    aprovado_por=aprovador,
                    decisao='aprovado',
                    comentario=random.choice(comentarios_aprovacao),
                )
                total_aprovacoes += 1

                StatusHistory.objects.create(
                    work_order=wo,
                    status_anterior='pendente',
                    status_novo='aprovado',
                    alterado_por=aprovador,
                    observacao=f'Aprovado por {aprovador.get_full_name()}',
                )
                total_historico += 1

                # Notificação para solicitante
                Notificacao.objects.create(
                    usuario=solicitante,
                    tipo='pedido_aprovado',
                    titulo=f'Pedido {codigo} aprovado!',
                    mensagem=f'Seu pedido {codigo} foi aprovado por {aprovador.get_full_name()}.',
                    work_order=wo,
                    lida=random.choice([True, False]),
                )
                total_notificacoes += 1

            # ── Transição: pendente → reprovado ──
            elif status_final in ['reprovado', 'reaprovacao']:
                wo.status = 'reprovado'
                wo.data_aprovacao = wo.data_envio + timedelta(hours=random.randint(4, 48))
                wo.save()

                comentarios_reprovacao = [
                    'Documentação incompleta. Favor revisar e reenviar.',
                    'Valores acima do limite aprovado para esta fase.',
                    'Necessário incluir mais cotações para análise.',
                    'Especificações técnicas precisam ser revisadas.',
                    'Falta justificativa técnica detalhada.',
                ]
                approval = Approval.objects.create(
                    work_order=wo,
                    aprovado_por=aprovador,
                    decisao='reprovado',
                    comentario=random.choice(comentarios_reprovacao),
                )
                total_aprovacoes += 1

                # Adicionar tags de erro à reprovação
                tags_disponiveis = list(TagErro.objects.filter(
                    tipo_solicitacao=cenario['tipo'], ativo=True
                ))
                if tags_disponiveis:
                    tags_selecionadas = random.sample(
                        tags_disponiveis,
                        min(random.randint(1, 3), len(tags_disponiveis))
                    )
                    approval.tags_erro.set(tags_selecionadas)

                StatusHistory.objects.create(
                    work_order=wo,
                    status_anterior='pendente',
                    status_novo='reprovado',
                    alterado_por=aprovador,
                    observacao=f'Reprovado por {aprovador.get_full_name()}',
                )
                total_historico += 1

                Notificacao.objects.create(
                    usuario=solicitante,
                    tipo='pedido_reprovado',
                    titulo=f'Pedido {codigo} reprovado',
                    mensagem=f'Seu pedido {codigo} foi reprovado por {aprovador.get_full_name()}. Verifique os motivos.',
                    work_order=wo,
                    lida=False,
                )
                total_notificacoes += 1

                # ── Transição: reprovado → reaprovação ──
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

                    # Comentário do solicitante
                    Comment.objects.create(
                        work_order=wo,
                        autor=solicitante,
                        texto='Corrigi os pontos apontados na reprovação. Por favor, reavaliar.',
                    )
                    total_comentarios += 1

            # ── Cancelamento ──
            elif status_final == 'cancelado':
                status_anterior = wo.status
                wo.status = 'cancelado'
                wo.save()

                motivos_cancelamento = [
                    'Escopo do projeto foi alterado. Serviço não é mais necessário.',
                    'Obra paralisada temporariamente por decisão da diretoria.',
                    'Substituído por outro pedido com valores atualizados.',
                ]
                StatusHistory.objects.create(
                    work_order=wo,
                    status_anterior=status_anterior,
                    status_novo='cancelado',
                    alterado_por=solicitante,
                    observacao=random.choice(motivos_cancelamento),
                )
                total_historico += 1

            # ── Comentários genéricos (nos pedidos não-rascunho) ──
            if status_final != 'rascunho' and random.random() > 0.4:
                comentarios_genericos = [
                    ('Preciso desse pedido com urgência para não atrasar o cronograma.', solicitante),
                    ('Favor verificar se o valor inclui BDI.', aprovador),
                    ('A equipe de campo já está aguardando essa definição.', solicitante),
                    ('Vou analisar com atenção e retorno em breve.', aprovador),
                    ('Segue em anexo o memorial descritivo atualizado.', solicitante),
                    ('Verificar disponibilidade do fornecedor para o prazo informado.', aprovador),
                ]
                num_comments = random.randint(1, 3)
                for _ in range(num_comments):
                    texto, autor = random.choice(comentarios_genericos)
                    Comment.objects.create(
                        work_order=wo,
                        autor=autor,
                        texto=texto,
                    )
                    total_comentarios += 1

        self.stdout.write(self.style.SUCCESS(f'   {total_pedidos} pedidos criados'))
        self.stdout.write(self.style.SUCCESS(f'   {total_aprovacoes} aprovacoes/reprovacoes'))
        self.stdout.write(self.style.SUCCESS(f'   {total_comentarios} comentarios'))
        self.stdout.write(self.style.SUCCESS(f'   {total_notificacoes} notificacoes'))
        self.stdout.write(self.style.SUCCESS(f'   {total_historico} registros de historico'))
