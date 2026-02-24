"""
Verifica integridade e consistência dos dados do Mapa de Suprimentos.

Checa:
- RecebimentoObra: quantidade_recebida + saldo coerente com quantidade_solicitada
- RecebimentoObra: sem valores negativos
- ItemMapa com numero_sc: recebimento_vinculado existe e bate
- AlocacaoRecebimento: soma por recebimento não ultrapassa quantidade_recebida
- Insumo: codigo_sienge sem duplicados
- RecebimentoObra: numero_sc preenchido

Uso:
    python manage.py verificar_mapa_suprimentos
    python manage.py verificar_mapa_suprimentos --verbose
"""
import sys
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Sum, Count, Q
from suprimentos.models import RecebimentoObra, ItemMapa, AlocacaoRecebimento, Insumo


def run_verificacao(verbose=False):
    """
    Executa todas as checagens de consistência do Mapa de Suprimentos.
    Retorna (erros, avisos) para uso em comando ou testes.
    """
    erros = []
    avisos = []

    # 1) RecebimentoObra: quantidades não negativas
    neg_solic = RecebimentoObra.objects.filter(quantidade_solicitada__lt=0)
    neg_rec = RecebimentoObra.objects.filter(quantidade_recebida__lt=0)
    neg_saldo = RecebimentoObra.objects.filter(saldo_a_entregar__lt=0)
    for qs, nome in [(neg_solic, 'quantidade_solicitada'), (neg_rec, 'quantidade_recebida'), (neg_saldo, 'saldo_a_entregar')]:
        n = qs.count()
        if n:
            erros.append(f'RecebimentoObra com {nome} negativa: {n} registro(s)')
            if verbose:
                for r in qs[:5]:
                    erros.append(f'   id={r.id} obra={r.obra_id} sc={r.numero_sc}')

    # 2) RecebimentoObra: quantidade_recebida + saldo_a_entregar <= quantidade_solicitada (coerência)
    for rec in RecebimentoObra.objects.all():
        qs = rec.quantidade_solicitada or Decimal('0.00')
        qr = rec.quantidade_recebida or Decimal('0.00')
        sa = rec.saldo_a_entregar or Decimal('0.00')
        if qr + sa > qs + Decimal('0.01'):  # tolerância 0.01
            erros.append(
                f'RecebimentoObra id={rec.id} SC={rec.numero_sc}: '
                f'recebido+saldo ({qr}+{sa}) > solicitado ({qs})'
            )
        if qr > qs + Decimal('0.01'):
            avisos.append(
                f'RecebimentoObra id={rec.id}: quantidade_recebida ({qr}) > quantidade_solicitada ({qs})'
            )

    # 3) ItemMapa com numero_sc: deve ter recebimento_vinculado
    itens_com_sc = ItemMapa.objects.exclude(numero_sc='').exclude(numero_sc__isnull=True)
    itens_com_sc_list = list(itens_com_sc)
    sem_vinculo = 0
    for item in itens_com_sc_list:
        rec = item.recebimento_vinculado
        if not rec:
            sem_vinculo += 1
            if verbose:
                erros.append(
                    f'ItemMapa id={item.id} obra={item.obra_id} insumo={item.insumo_id} '
                    f'sc={item.numero_sc} sem RecebimentoObra vinculado'
                )
    if sem_vinculo and not verbose:
        erros.append(f'ItemMapa com numero_sc sem RecebimentoObra vinculado: {sem_vinculo}')

    # 4) AlocacaoRecebimento: soma por recebimento não pode ultrapassar quantidade_recebida
    for rec in RecebimentoObra.objects.filter(quantidade_recebida__gt=0):
        total_aloc = AlocacaoRecebimento.objects.filter(recebimento=rec).aggregate(
            total=Sum('quantidade_alocada')
        )['total'] or Decimal('0.00')
        if total_aloc > (rec.quantidade_recebida or Decimal('0.00')) + Decimal('0.01'):
            erros.append(
                f'RecebimentoObra id={rec.id} SC={rec.numero_sc}: '
                f'soma alocações ({total_aloc}) > quantidade_recebida ({rec.quantidade_recebida})'
            )

    # 4b) AlocacaoRecebimento: integridade (obra/insumo do item_mapa e do recebimento batem)
    for aloc in AlocacaoRecebimento.objects.select_related('obra', 'insumo', 'recebimento', 'item_mapa').all():
        if not aloc.item_mapa_id or not aloc.recebimento_id:
            continue
        if aloc.item_mapa.obra_id != aloc.obra_id or aloc.item_mapa.insumo_id != aloc.insumo_id:
            erros.append(
                f'AlocacaoRecebimento id={aloc.id}: item_mapa (obra={aloc.item_mapa.obra_id}, insumo={aloc.item_mapa.insumo_id}) '
                f'não bate com alocação (obra={aloc.obra_id}, insumo={aloc.insumo_id})'
            )
        if aloc.recebimento.obra_id != aloc.obra_id or aloc.recebimento.insumo_id != aloc.insumo_id:
            erros.append(
                f'AlocacaoRecebimento id={aloc.id}: recebimento (obra={aloc.recebimento.obra_id}, insumo={aloc.recebimento.insumo_id}) '
                f'não bate com alocação (obra={aloc.obra_id}, insumo={aloc.insumo_id})'
            )
        if (aloc.quantidade_alocada or Decimal('0.00')) <= Decimal('0'):
            avisos.append(f'AlocacaoRecebimento id={aloc.id}: quantidade_alocada <= 0')

    # 4c) Coerência forte: recebido + saldo_a_entregar deveria ≈ quantidade_solicitada (processo: o que foi pedido = o que chegou + o que falta chegar)
    for rec in RecebimentoObra.objects.all():
        qs = rec.quantidade_solicitada or Decimal('0.00')
        qr = rec.quantidade_recebida or Decimal('0.00')
        sa = rec.saldo_a_entregar or Decimal('0.00')
        if qs > Decimal('0') and abs((qr + sa) - qs) > Decimal('0.01'):
            avisos.append(
                f'RecebimentoObra id={rec.id} SC={rec.numero_sc}: '
                f'recebido+saldo ({qr}+{sa}) ≠ solicitado ({qs}) — conferir se é intencional'
            )

    # 5) RecebimentoObra: numero_sc preenchido
    rec_sem_sc = RecebimentoObra.objects.filter(Q(numero_sc='') | Q(numero_sc__isnull=True))
    n_sem_sc = rec_sem_sc.count()
    if n_sem_sc:
        erros.append(f'RecebimentoObra com numero_sc vazio: {n_sem_sc}')

    # 6) Insumos sem código duplicado
    duplicados = Insumo.objects.values('codigo_sienge').annotate(c=Count('id')).filter(c__gt=1)
    if duplicados.exists():
        erros.append(f'Insumo com codigo_sienge duplicado: {list(duplicados)}')

    return erros, avisos


class Command(BaseCommand):
    help = 'Verifica consistência dos dados do Mapa de Suprimentos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Lista cada problema encontrado',
        )

    def handle(self, *args, **options):
        verbose = options.get('verbose', False)
        erros, avisos = run_verificacao(verbose=verbose)

        # Resumo
        self.stdout.write(self.style.SUCCESS('\n🔍 VERIFICAÇÃO MAPA DE SUPRIMENTOS\n'))
        if erros:
            self.stdout.write(self.style.ERROR(f'   ❌ Erros: {len(erros)}'))
            for e in erros[:30]:
                self.stdout.write(self.style.ERROR(f'      {e}'))
            if len(erros) > 30:
                self.stdout.write(self.style.ERROR(f'      ... e mais {len(erros) - 30}'))
        else:
            self.stdout.write(self.style.SUCCESS('   ✅ Nenhum erro de consistência encontrado.'))

        if avisos:
            self.stdout.write(self.style.WARNING(f'\n   ⚠️ Avisos: {len(avisos)}'))
            for a in avisos[:10]:
                self.stdout.write(self.style.WARNING(f'      {a}'))

        # Contagens
        self.stdout.write(self.style.SUCCESS('\n📊 Contagens:'))
        self.stdout.write(f'   RecebimentoObra: {RecebimentoObra.objects.count()}')
        self.stdout.write(f'   ItemMapa: {ItemMapa.objects.count()}')
        self.stdout.write(f'   ItemMapa com SC: {ItemMapa.objects.exclude(numero_sc="").exclude(numero_sc__isnull=True).count()}')
        self.stdout.write(f'   AlocacaoRecebimento: {AlocacaoRecebimento.objects.count()}')

        if erros:
            self.stdout.write(self.style.ERROR('\n❌ Verificação falhou. Corrija os dados antes de seguir.\n'))
            sys.exit(1)
        self.stdout.write(self.style.SUCCESS('\n✅ Dados consistentes. Pode seguir para o próximo sistema.\n'))
