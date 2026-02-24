"""
Coloca alguns itens para fora da fase "Levantamento" com dados genéricos,
para visualizar o dashboard com Comprado / No Pátio / Alocado.

- Escolhe itens que estão só em Levantamento (sem numero_sc, com quantidade_planejada > 0).
- Cria SC + RecebimentoObra com quantidades variadas (0%, 40%, 70%, 100% recebido).
- Para parte deles cria AlocacaoRecebimento (rateio no local).

Uso:
    python manage.py seed_dashboard_fases
    python manage.py seed_dashboard_fases --confirmar
    python manage.py seed_dashboard_fases --confirmar --obra 12
    python manage.py seed_dashboard_fases --confirmar --max 20
"""
from decimal import Decimal
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from mapa_obras.models import Obra
from suprimentos.models import ItemMapa, RecebimentoObra, AlocacaoRecebimento

FORNECEDORES = [
    'Construtora Materiais Ltda',
    'Cimento Nacional S.A.',
    'Ferragens & Aço Ltda',
    'Cerâmica São Paulo',
]

# (label, % recebido, % alocado do recebido)
CENARIOS = [
    ('comprado_aguardando', Decimal('0.00'), Decimal('0.00')),   # Só tem SC, nada recebido
    ('parcial_patio', Decimal('0.40'), Decimal('0.00')),        # 40% no pátio, nada alocado
    ('parcial_alocado', Decimal('0.70'), Decimal('0.50')),     # 70% recebido, 50% disso alocado
    ('completo', Decimal('1.00'), Decimal('1.00')),            # 100% recebido e alocado
    ('completo_parcial_alocado', Decimal('1.00'), Decimal('0.60')),  # 100% recebido, 60% alocado
]


class Command(BaseCommand):
    help = 'Avança itens da fase Levantamento para Comprado/No Pátio/Alocado (dados genéricos)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Aplicar alterações (sem isso só mostra o que seria feito)',
        )
        parser.add_argument(
            '--obra',
            type=int,
            default=0,
            help='ID da obra (0 = todas)',
        )
        parser.add_argument(
            '--max',
            type=int,
            default=12,
            help='Máximo de (obra, insumo) a avançar',
        )

    def handle(self, *args, **options):
        confirmar = options.get('confirmar', False)
        obra_id = options.get('obra', 0)
        max_pares = options.get('max', 12)

        if not confirmar:
            self.stdout.write(self.style.WARNING(
                '\n⚠️  MODO SIMULAÇÃO. Use --confirmar para aplicar.\n'
            ))

        obras = Obra.objects.all().order_by('id')
        if obra_id:
            obras = obras.filter(id=obra_id)
        obras = list(obras)
        if not obras:
            self.stdout.write(self.style.ERROR('Nenhuma obra encontrada.'))
            return

        # (obra_id, insumo_id) em Levantamento: sem numero_sc, com quantidade_planejada > 0
        pares_levantamento = list(
            dict.fromkeys(
                ItemMapa.objects.filter(
                    obra__in=obras,
                    quantidade_planejada__gt=0,
                    nao_aplica=False,
                ).filter(Q(numero_sc__isnull=True) | Q(numero_sc=''))
                .values_list('obra_id', 'insumo_id', flat=False)
            )
        )[:max_pares]
        if not pares_levantamento:
            self.stdout.write(self.style.WARNING(
                'Nenhum item em fase Levantamento (sem SC) com quantidade planejada > 0.'
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            f'\n📊 Seed dashboard fases\n   Obras: {len(obras)}\n   Par (obra, insumo) a avançar: {len(pares_levantamento)}\n'
        ))

        if not confirmar:
            for (oid, iid) in pares_levantamento[:5]:
                self.stdout.write(f'   Ex.: obra_id={oid}, insumo_id={iid}')
            self.stdout.write(self.style.WARNING('\n💡 python manage.py seed_dashboard_fases --confirmar\n'))
            return

        hoje = date.today()
        total_receb = 0
        total_aloc = 0
        sc_base = 9000
        criados = []

        with transaction.atomic():
            for idx, (ob_id, ins_id) in enumerate(pares_levantamento):
                obra = next((o for o in obras if o.id == ob_id), None)
                if not obra:
                    continue
                itens = list(
                    ItemMapa.objects.filter(
                        obra_id=ob_id,
                        insumo_id=ins_id,
                    ).select_related('insumo', 'local_aplicacao').order_by('id')
                )
                if not itens:
                    continue
                primeiro = itens[0]
                insumo = primeiro.insumo
                qtd_planejada = sum((i.quantidade_planejada or Decimal('0.00')) for i in itens)
                if qtd_planejada <= 0:
                    continue
                quantidade_solicitada = qtd_planejada
                cenario = CENARIOS[idx % len(CENARIOS)]
                nome_cenario, pct_recebido, pct_alocado = cenario
                quantidade_recebida = (quantidade_solicitada * pct_recebido).quantize(Decimal('0.01'))
                saldo_a_entregar = max(Decimal('0.00'), quantidade_solicitada - quantidade_recebida)

                sc_base += 1
                numero_sc = f'SC-DEMO-{sc_base}'
                numero_pc = f'PC-DEMO-{sc_base}'
                data_sc = hoje - timedelta(days=20)
                data_pc = hoje - timedelta(days=10)
                prazo_recebimento = hoje + (timedelta(days=5) if quantidade_recebida == 0 else timedelta(days=-3))
                fornecedor = FORNECEDORES[idx % len(FORNECEDORES)]
                numero_nf = f'NF-DEMO-{1000 + sc_base}' if quantidade_recebida > 0 else ''
                data_nf = (hoje - timedelta(days=2)) if quantidade_recebida > 0 else None

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
                    descricao_item=insumo.descricao or '',
                    quantidade_solicitada=quantidade_solicitada,
                    quantidade_recebida=quantidade_recebida,
                    saldo_a_entregar=saldo_a_entregar,
                    numero_nf=numero_nf,
                    data_nf=data_nf,
                )
                total_receb += 1

                n_atualizados = ItemMapa.objects.filter(obra=obra, insumo=insumo).update(
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
                criados.append((numero_sc, numero_pc, obra.nome[:30], insumo.descricao[:40] if insumo.descricao else '-', n_atualizados))

                if quantidade_recebida > 0 and pct_alocado > 0:
                    qtd_aloc_total = (quantidade_recebida * pct_alocado).quantize(Decimal('0.01'))
                    if qtd_aloc_total >= Decimal('0.01'):
                        itens_com_local = [i for i in itens if i.local_aplicacao_id]
                        if itens_com_local:
                            item_dest = itens_com_local[0]
                            AlocacaoRecebimento.objects.create(
                                obra=obra,
                                insumo=insumo,
                                local_aplicacao=item_dest.local_aplicacao,
                                recebimento=rec,
                                item_mapa=item_dest,
                                quantidade_alocada=qtd_aloc_total,
                            )
                            total_aloc += 1

        for sc, pc, ob_nome, ins_nome, n in criados[:10]:
            self.stdout.write(f'   {sc} / {pc}  →  obra "{ob_nome}"  insumo "{ins_nome}"  ({n} itens)')
        if len(criados) > 10:
            self.stdout.write(f'   ... e mais {len(criados) - 10} pares.')

        n_com_sc = ItemMapa.objects.filter(numero_sc__startswith='SC-DEMO-').count()
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Concluído: {total_receb} RecebimentoObra, {total_aloc} AlocacaoRecebimento.\n'
            f'   ItemMapa com SC-DEMO-* no banco: {n_com_sc}.\n'
            '   Atualize o dashboard (F5) e escolha uma obra para ver Comprado / No Pátio / Alocado.\n'
        ))
