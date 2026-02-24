"""
Comando para popular o banco com dados de teste realistas.
Útil para testar o sistema sem integração com Sienge.

NOVA ARQUITETURA:
- RecebimentoObra: Representa o que CHEGOU na obra (vem do Sienge)
- AlocacaoRecebimento: Distribui o recebido para locais específicos (manual)
- ItemMapa: Planejamento por local (quantidade_alocada_local calculada)

Uso:
    python manage.py seed_teste              # Cria dados padrão
    python manage.py seed_teste --limpar     # Limpa e recria tudo
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.db import transaction
from obras.models import Obra, LocalObra
from suprimentos.models import Insumo, ItemMapa, RecebimentoObra, AlocacaoRecebimento
from decimal import Decimal
from datetime import date, timedelta
import random


class Command(BaseCommand):
    help = 'Popula o banco com dados de teste realistas para testar sem Sienge'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpar',
            action='store_true',
            help='Limpa dados existentes antes de criar novos'
        )

    def handle(self, *args, **options):
        if options['limpar']:
            self.stdout.write('🗑️ Limpando dados existentes...')
            AlocacaoRecebimento.objects.all().delete()
            RecebimentoObra.objects.all().delete()
            ItemMapa.objects.all().delete()
            Insumo.objects.all().delete()
            LocalObra.objects.all().delete()
            Obra.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('   ✅ Dados limpos!'))

        with transaction.atomic():
            self.criar_grupos()
            self.criar_usuarios()
            self.criar_obras()
            self.criar_insumos()
            self.criar_itens_e_recebimentos()

        self.stdout.write(self.style.SUCCESS('\n✅ Seed concluído! Sistema pronto para testes.'))
        self.stdout.write('\n📋 Usuários de teste:')
        self.stdout.write('   engenheiro / eng123 (grupo ENGENHARIA)')
        self.stdout.write('   chefe / chefe123 (grupo CHEFIA)')
        self.stdout.write('   admin / admin (superuser)')
        self.stdout.write('\n📊 Nova Arquitetura:')
        self.stdout.write('   - RecebimentoObra: O que chegou na obra (sem local específico)')
        self.stdout.write('   - AlocacaoRecebimento: Distribuição manual para locais')
        self.stdout.write('   - ItemMapa: Planejamento por local (quantidade_alocada_local calculada)')

    def criar_grupos(self):
        self.stdout.write('👥 Criando grupos...')
        Group.objects.get_or_create(name='ENGENHARIA')
        Group.objects.get_or_create(name='CHEFIA')
        self.stdout.write(self.style.SUCCESS('   ✅ Grupos criados'))

    def criar_usuarios(self):
        self.stdout.write('👤 Criando usuários de teste...')
        
        # Engenheiro
        eng, created = User.objects.get_or_create(
            username='engenheiro',
            defaults={
                'first_name': 'João',
                'last_name': 'Engenheiro',
                'email': 'engenheiro@teste.com',
                'is_staff': False
            }
        )
        if created:
            eng.set_password('eng123')
            eng.save()
        eng.groups.add(Group.objects.get(name='ENGENHARIA'))
        
        # Chefe
        chefe, created = User.objects.get_or_create(
            username='chefe',
            defaults={
                'first_name': 'Maria',
                'last_name': 'Gerente',
                'email': 'chefe@teste.com',
                'is_staff': False
            }
        )
        if created:
            chefe.set_password('chefe123')
            chefe.save()
        chefe.groups.add(Group.objects.get(name='CHEFIA'))
        
        # Admin
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'first_name': 'Admin',
                'last_name': 'Sistema',
                'email': 'admin@teste.com',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            admin.set_password('admin')
            admin.save()
        
        self.stdout.write(self.style.SUCCESS('   ✅ Usuários criados'))

    def criar_obras(self):
        self.stdout.write('🏗️ Criando obras...')
        
        obras_data = [
            ('224', 'Residencial Parque das Flores', [
                ('Bloco A', 'BLOCO'),
                ('Bloco B', 'BLOCO'),
                ('Bloco C', 'BLOCO'),
                ('Área Comum', 'SETOR'),
            ]),
            ('300', 'Comercial Centro Empresarial', [
                ('Torre Norte', 'BLOCO'),
                ('Torre Sul', 'BLOCO'),
                ('Estacionamento', 'SETOR'),
                ('Lobby', 'SETOR'),
            ]),
            ('450', 'Industrial Galpão Logístico', [
                ('Galpão 1', 'SETOR'),
                ('Galpão 2', 'SETOR'),
                ('Área Administrativa', 'SETOR'),
                ('Doca', 'SETOR'),
            ]),
        ]
        
        for codigo, nome, locais in obras_data:
            obra, _ = Obra.objects.get_or_create(
                codigo_sienge=codigo,
                defaults={'nome': nome, 'ativa': True}
            )
            for local_nome, tipo in locais:
                LocalObra.objects.get_or_create(
                    obra=obra,
                    nome=local_nome,
                    tipo=tipo
                )
            self.stdout.write(f'   ✅ {codigo} - {nome} ({len(locais)} locais)')

    def criar_insumos(self):
        """
        Cria catálogo de insumos (simulando importação do Sienge).
        
        NOTA: Insumo NÃO tem categoria - a categoria é definida no ItemMapa,
        porque o mesmo insumo pode ser usado em diferentes categorias
        (ex: Cimento pode ser usado em FUNDAÇÃO, ESTRUTURA, ALVENARIA).
        """
        self.stdout.write('📦 Criando insumos (catálogo Sienge)...')
        
        # Dados simulando CSV do Sienge: (código, descrição, unidade)
        insumos_data = [
            # Concretos
            ('5926', 'CIMENTO PORTLAND COMPOSTO CP II-32', 'KG'),
            ('5927', 'CONCRETO USINADO FCK 30 MPA', 'M³'),
            ('5928', 'CONCRETO USINADO FCK 35 MPA', 'M³'),
            
            # Aços
            ('6001', 'AÇO CA-50 12.5MM', 'KG'),
            ('6002', 'AÇO CA-60 5.0MM', 'KG'),
            ('6003', 'AÇO CA-50 10.0MM', 'KG'),
            
            # Formas e Estruturas
            ('7001', 'FORMA DE MADEIRA COMPENSADA 18MM', 'M²'),
            ('7002', 'ESCORAMENTO METÁLICO', 'M²'),
            ('7003', 'LAJE TRELIÇADA H12', 'M²'),
            ('7004', 'ESTACA PRÉ-MOLDADA 30X30', 'M'),
            
            # Alvenaria
            ('8001', 'BLOCO CERÂMICO 14X19X29', 'UND'),
            ('8002', 'ARGAMASSA DE ASSENTAMENTO', 'KG'),
            ('8003', 'VERGA PRÉ-MOLDADA 1.20M', 'UND'),
            
            # Instalações Elétricas
            ('9001', 'CABO ELÉTRICO 4MM² FLEXÍVEL', 'M'),
            ('9002', 'QUADRO DE DISTRIBUIÇÃO 24 DISJUNTORES', 'UND'),
            ('9003', 'DISJUNTOR BIPOLAR 32A', 'UND'),
            
            # Instalações Hidráulicas
            ('9101', 'TUBO PVC 100MM ESGOTO', 'M'),
            ('9102', 'CAIXA D\'ÁGUA 1000L', 'UND'),
            ('9103', 'REGISTRO GAVETA 1"', 'UND'),
            
            # Acabamentos
            ('10001', 'PORCELANATO 60X60 POLIDO', 'M²'),
            ('10002', 'TINTA ACRÍLICA PREMIUM BRANCA 18L', 'L'),
            ('10003', 'PORTA DE MADEIRA 80X210', 'UND'),
            ('10004', 'JANELA ALUMÍNIO 120X120', 'UND'),
            
            # Outros
            ('16085', 'GRADE DE PORTA DE MADEIRA / TAM: 0,80 X 2,10', 'UND'),
            ('4364', 'CAIXA D\'ÁGUA EM POLIETILENO 5000 LITROS, COM TAMPA', 'UND'),
            ('16112', 'CAIXA D\'ÁGUA EM POLIETILENO 1000 LITROS, COM TAMPA', 'UND'),
            ('16070', 'PASTA CATÁLOGO - A4', 'UND'),
            ('14418', 'MONITOR AUXILIAR', 'UND'),
            ('14433', 'NOTEBOOK', 'UND'),
        ]
        
        for codigo, descricao, unidade in insumos_data:
            Insumo.objects.get_or_create(
                codigo_sienge=codigo,
                defaults={
                    'descricao': descricao,
                    'unidade': unidade,
                    'ativo': True
                }
            )
        
        self.stdout.write(self.style.SUCCESS(f'   ✅ {len(insumos_data)} insumos criados'))

    def criar_itens_e_recebimentos(self):
        """
        NOVA ARQUITETURA:
        1. Cria ItemMapa (planejamento por local)
        2. Cria RecebimentoObra (o que chegou na obra - simulando Sienge)
        3. Cria AlocacaoRecebimento (distribuição manual para locais)
        """
        self.stdout.write('📝 Criando itens do mapa com nova arquitetura...')
        
        obras = Obra.objects.filter(ativa=True)
        insumos = list(Insumo.objects.filter(ativo=True))
        hoje = date.today()
        user = User.objects.filter(is_superuser=True).first()
        
        # Status simulados para variedade
        # (tem_sc, tem_pc, recebido_obra_percent, alocado_percent, dias_prazo)
        status_configs = [
            (False, False, 0, 0, 30),       # BRANCO - A levantar (sem SC)
            (True, False, 0, 0, 20),         # VERMELHO - Solicitado (SC sem PC)
            (True, True, 0, 0, 15),          # AMARELO (claro) - PC sem recebimento
            (True, True, 0.8, 0, 10),        # AMARELO - Chegou na obra mas não alocou
            (True, True, 0.8, 0.5, 5),       # LARANJA - Alocação parcial
            (True, True, 1.0, 1.0, -5),      # VERDE - Totalmente alocado
            (True, True, 0.5, 0, -10),       # ATRASADO - Chegou parcial
        ]
        
        total_itens = 0
        total_recebimentos = 0
        total_alocacoes = 0
        
        # Categorias de aplicação (onde o insumo será usado na obra)
        categorias_aplicacao = ['FUNDAÇÃO', 'ESTRUTURA', 'ALVENARIA', 'INSTALAÇÕES ELÉTRICAS', 
                                'INSTALAÇÕES HIDRÁULICAS', 'ACABAMENTO', 'COBERTURA']
        
        for obra in obras:
            locais = list(obra.locais.all())
            if not locais:
                continue
            
            sc_counter = 100
            
            for insumo in insumos:
                # Criar 1-2 itens por insumo por obra
                num_itens = random.randint(1, 2)
                
                for i in range(num_itens):
                    local = random.choice(locais)
                    config = random.choice(status_configs)
                    tem_sc, tem_pc, recebido_percent, alocado_percent, dias = config
                    
                    quantidade_planejada = Decimal(str(random.randint(50, 500)))
                    numero_sc = f'SC{sc_counter}' if tem_sc else ''
                    numero_pc = f'PC{random.randint(100, 999)}' if tem_pc else ''
                    fornecedor = random.choice(['Concreteira ABC', 'Ferragem XYZ', 'Materiais 123', 'Fornecedor Delta']) if tem_pc else ''
                    prazo = hoje + timedelta(days=dias) if tem_pc else None
                    
                    # Escolher categoria de aplicação (onde vai usar o insumo)
                    # 20% dos itens ficam como "A CLASSIFICAR" (simulando importação do Sienge)
                    if random.random() < 0.2:
                        categoria = 'A CLASSIFICAR'
                    else:
                        categoria = random.choice(categorias_aplicacao)
                    
                    # === 1. CRIAR ITEMMAPA (Planejamento) ===
                    item = ItemMapa.objects.create(
                        obra=obra,
                        insumo=insumo,
                        categoria=categoria,  # Categoria = onde vai aplicar (não vem do insumo!)
                        local_aplicacao=local,
                        responsavel=random.choice(['João Silva', 'Maria Santos', 'Pedro Costa']),
                        prazo_necessidade=hoje + timedelta(days=random.randint(5, 60)),
                        quantidade_planejada=quantidade_planejada,
                        prioridade=random.choice(['URGENTE', 'ALTA', 'MEDIA', 'BAIXA']),
                        numero_sc=numero_sc,
                        # Campos legados (mantidos para compatibilidade)
                        numero_pc=numero_pc,
                        empresa_fornecedora=fornecedor,
                        prazo_recebimento=prazo,
                    )
                    total_itens += 1
                    
                    # === 2. CRIAR RECEBIMENTOOBRA (o que veio do Sienge) ===
                    if tem_sc:
                        quantidade_recebida = quantidade_planejada * Decimal(str(recebido_percent))
                        saldo = quantidade_planejada - quantidade_recebida
                        
                        recebimento, rec_created = RecebimentoObra.objects.get_or_create(
                            obra=obra,
                            numero_sc=numero_sc,
                            defaults={
                                'insumo': insumo,
                                'data_sc': hoje - timedelta(days=random.randint(10, 30)),
                                'numero_pc': numero_pc,
                                'data_pc': hoje - timedelta(days=random.randint(5, 20)) if tem_pc else None,
                                'empresa_fornecedora': fornecedor,
                                'prazo_recebimento': prazo,
                                'quantidade_solicitada': quantidade_planejada,
                                'quantidade_recebida': quantidade_recebida,
                                'saldo_a_entregar': saldo,
                            }
                        )
                        
                        if rec_created:
                            total_recebimentos += 1
                        
                        # Atualizar campos legados do ItemMapa
                        item.quantidade_recebida = quantidade_recebida
                        item.saldo_a_entregar = saldo
                        item.save()
                        
                        # === 3. CRIAR ALOCAÇÃO (se houver recebimento e alocação) ===
                        if recebido_percent > 0 and alocado_percent > 0:
                            qtd_alocar = quantidade_planejada * Decimal(str(alocado_percent))
                            
                            alocacao = AlocacaoRecebimento.objects.create(
                                obra=obra,
                                insumo=insumo,
                                local_aplicacao=local,
                                recebimento=recebimento,
                                item_mapa=item,
                                quantidade_alocada=qtd_alocar,
                                observacao=f'Alocação automática seed - {hoje}',
                                criado_por=user
                            )
                            total_alocacoes += 1
                    
                    sc_counter += 1
        
        self.stdout.write(self.style.SUCCESS(f'   ✅ {total_itens} itens de mapa criados'))
        self.stdout.write(self.style.SUCCESS(f'   ✅ {total_recebimentos} recebimentos na obra criados'))
        self.stdout.write(self.style.SUCCESS(f'   ✅ {total_alocacoes} alocações para locais criadas'))

