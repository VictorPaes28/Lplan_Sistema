"""
Simula dados fictícios do Sienge para testar o Mapa de Suprimentos.

Cria RecebimentoObra com:
- Nº SC, PC, datas, fornecedor
- Quantidade solicitada / recebida / saldo (completo, parcial, atraso)
- Alguns com prazo_recebimento no passado (atraso)
- Opcionalmente AlocacaoRecebimento (rateio por local)

Requer que mapa_suprimentos_apenas_grosso já tenha sido executado (obras, itens, insumos).

Uso:
    python manage.py simular_sienge_demo
    python manage.py simular_sienge_demo --confirmar
"""
from decimal import Decimal
from datetime import date, timedelta
import random
from django.core.management.base import BaseCommand
from django.db import transaction
from mapa_obras.models import Obra
from suprimentos.models import (
    ItemMapa,
    RecebimentoObra,
    AlocacaoRecebimento,
)

# Fornecedores fictícios
FORNECEDORES = [
    'Construtora Materiais Ltda',
    'Cimento Nacional S.A.',
    'Ferragens & Aço Ltda',
    'Cerâmica São Paulo',
    'Distribuidora de Revestimentos',
]

# Cenários: (nome, % recebido, atraso_em_dias, tem_pc)
# atraso_em_dias: negativo = prazo no passado (atrasado)
CENARIOS = [
    ('completo', Decimal('1.00'), 0, True),       # 100% recebido, no prazo
    ('completo_atrasado', Decimal('1.00'), -15, True),  # 100% mas chegou atrasado
    ('parcial', Decimal('0.60'), 5, True),         # 60% recebido, resto a caminho
    ('parcial_atrasado', Decimal('0.40'), -7, True),   # 40% recebido, atrasado
    ('aguardando', Decimal('0.00'), 10, True),    # 0% recebido, no prazo
    ('atrasado_sem_entrega', Decimal('0.00'), -20, True),  # 0%, prazo vencido
]


class Command(BaseCommand):
    help = 'Simula recebimentos e dados Sienge fictícios para teste'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Executa a simulação (sem isso, apenas mostra o que seria feito)',
        )
        parser.add_argument(
            '--obras',
            type=int,
            default=0,
            help='Quantidade de obras a popular (0 = todas)',
        )

    def handle(self, *args, **options):
        confirmar = options.get('confirmar', False)
        limit_obras = options.get('obras', 0)

        if not confirmar:
            self.stdout.write(self.style.WARNING(
                '\n⚠️  MODO SIMULAÇÃO - Nada será alterado.\n'
                'Use --confirmar para aplicar os dados fictícios.\n'
            ))

        obras = list(Obra.objects.all().order_by('id'))
        if limit_obras:
            obras = obras[:limit_obras]
        if not obras:
            self.stdout.write(self.style.ERROR('Nenhuma obra encontrada. Rode antes: mapa_suprimentos_apenas_grosso --confirmar'))
            return

        # Itens do mapa por obra (agrupados por obra, insumo - um ItemMapa por grupo para vincular SC)
        itens_por_obra_insumo = {}
        for obra in obras:
            itens = ItemMapa.objects.filter(obra=obra).select_related('insumo', 'local_aplicacao').order_by('insumo_id', 'id')
            for item in itens:
                key = (obra.id, item.insumo_id)
                if key not in itens_por_obra_insumo:
                    itens_por_obra_insumo[key] = list(ItemMapa.objects.filter(obra=obra, insumo=item.insumo).order_by('id'))

        # Escolher quais (obra, insumo) vão ganhar SC: ~50% dos itens únicos por obra
        pares_obra_insumo = list(itens_por_obra_insumo.keys())
        random.shuffle(pares_obra_insumo)
        n_simular = max(10, len(pares_obra_insumo) // 2)
        pares_a_simular = pares_obra_insumo[:n_simular]

        self.stdout.write(self.style.SUCCESS('\n📊 SIMULAÇÃO SIENGE (dados fictícios)\n'))
        self.stdout.write(f'   Obras: {len(obras)}')
        self.stdout.write(f'   Par (obra, insumo) a receber SC: {len(pares_a_simular)}')
        self.stdout.write('   Cenários: completo, parcial, atraso, aguardando entrega')

        if not confirmar:
            self.stdout.write(self.style.WARNING(
                '\n💡 Para aplicar: python manage.py simular_sienge_demo --confirmar\n'
            ))
            return

        hoje = date.today()
        total_receb = 0
        total_aloc = 0
        sc_global = 1000
        random.seed(42)  # reprodutível

        with transaction.atomic():
            for idx, (obra_id, insumo_id) in enumerate(pares_a_simular):
                obra = next((o for o in obras if o.id == obra_id), None)
                if not obra:
                    continue
                itens_mapa = itens_por_obra_insumo.get((obra_id, insumo_id), [])
                if not itens_mapa:
                    continue
                primeiro_item = itens_mapa[0]
                insumo = primeiro_item.insumo

                nome_cenario, pct_recebido, atraso_dias, tem_pc = random.choice(CENARIOS)
                qtd_base = random.choice([100, 250, 500, 1000, 2000, 5000])
                quantidade_solicitada = Decimal(str(qtd_base))
                quantidade_recebida = (quantidade_solicitada * pct_recebido).quantize(Decimal('0.01'))
                saldo_a_entregar = max(Decimal('0.00'), quantidade_solicitada - quantidade_recebida)

                sc_global += 1
                numero_sc = f'SC-2026-{sc_global}'
                numero_pc = f'PC-{sc_global}-{random.randint(100, 999)}' if tem_pc else ''
                data_sc = hoje - timedelta(days=random.randint(15, 45))
                data_pc = (hoje - timedelta(days=random.randint(5, 25))) if tem_pc else None
                prazo_recebimento = hoje + timedelta(days=atraso_dias)
                fornecedor = random.choice(FORNECEDORES)
                numero_nf = f'NF-{random.randint(10000, 99999)}' if quantidade_recebida > 0 else ''
                data_nf = (hoje - timedelta(days=random.randint(1, 10))) if quantidade_recebida > 0 else None

                rec = RecebimentoObra.objects.create(
                    obra=obra,
                    insumo=insumo,
                    item_sc='',
                    numero_sc=numero_sc,
                    data_sc=data_sc,
                    numero_pc=numero_pc,
                    data_pc=data_pc,
                    empresa_fornecedora=fornecedor,
                    prazo_recebimento=prazo_recebimento,
                    descricao_item=insumo.descricao,
                    quantidade_solicitada=quantidade_solicitada,
                    quantidade_recebida=quantidade_recebida,
                    saldo_a_entregar=saldo_a_entregar,
                    numero_nf=numero_nf,
                    data_nf=data_nf,
                )
                total_receb += 1

                # Vincular todos os ItemMapa (obra, insumo) a esta SC
                ItemMapa.objects.filter(obra=obra, insumo=insumo).update(
                    numero_sc=numero_sc,
                    item_sc='',
                    data_sc=data_sc,
                    numero_pc=numero_pc,
                    data_pc=data_pc,
                    empresa_fornecedora=fornecedor,
                    prazo_recebimento=prazo_recebimento,
                    quantidade_recebida=quantidade_recebida,
                    saldo_a_entregar=saldo_a_entregar,
                )

                # Criar alocação para alguns (rateio): só se recebeu algo e tem local
                if quantidade_recebida > 0 and len(itens_mapa) >= 1 and itens_mapa[0].local_aplicacao_id:
                    item_com_local = next((i for i in itens_mapa if i.local_aplicacao_id), None)
                    if item_com_local:
                        qtd_aloc = (quantidade_recebida * Decimal('0.5')).quantize(Decimal('0.01'))  # 50% para primeiro local
                        if qtd_aloc >= Decimal('0.01'):
                            AlocacaoRecebimento.objects.create(
                                obra=obra,
                                insumo=insumo,
                                local_aplicacao=item_com_local.local_aplicacao,
                                recebimento=rec,
                                item_mapa=item_com_local,
                                quantidade_alocada=qtd_aloc,
                            )
                            total_aloc += 1

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Simulação concluída: {total_receb} RecebimentoObra, {total_aloc} AlocacaoRecebimento.\n'
            '   Rode: python manage.py verificar_mapa_suprimentos\n'
        ))
