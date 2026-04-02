"""
Verificação de consistência do Mapa de Suprimentos (RecebimentoObra, ItemMapa, alocações).

Uso: python manage.py verificar_mapa_suprimentos

A função run_verificacao() é usada pelos testes em test_verificacao_mapa.py.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Sum

from suprimentos.models import (
    RecebimentoObra,
    ItemMapa,
    AlocacaoRecebimento,
)


def run_verificacao(verbose=False):
    """
    Retorna (erros, avisos) — listas de mensagens str.
    verbose reservado para logs extras no futuro.
    """
    _ = verbose
    erros = []
    avisos = []

    # 1) Coerência: recebido + saldo não pode ultrapassar o solicitado (com tolerância de arredondamento)
    for rec in RecebimentoObra.objects.select_related('obra', 'insumo'):
        sol = rec.quantidade_solicitada or Decimal('0')
        qrec = rec.quantidade_recebida or Decimal('0')
        saldo = rec.saldo_a_entregar or Decimal('0')
        if qrec + saldo > sol + Decimal('0.01'):
            erros.append(
                f'[{rec.obra.codigo_sienge}] SC {rec.numero_sc} insumo {rec.insumo.codigo_sienge}: '
                f'recebido+saldo ({qrec}+{saldo}) maior que solicitado ({sol})'
            )

    # 2) Item com SC deve ter RecebimentoObra vinculável (mesma lógica do modelo)
    for item in ItemMapa.objects.exclude(numero_sc='').filter(numero_sc__isnull=False).select_related(
        'obra', 'insumo'
    ):
        if item.recebimento_vinculado is None:
            erros.append(
                f'ItemMapa id={item.pk} (obra {item.obra_id}, insumo {item.insumo_id}): '
                f'numero_sc={item.numero_sc!r} sem RecebimentoObra vinculado'
            )

    # 3) Soma das alocações por recebimento não pode exceder o recebido na obra
    for rec in RecebimentoObra.objects.all():
        total_aloc = (
            AlocacaoRecebimento.objects.filter(recebimento=rec).aggregate(
                t=Sum('quantidade_alocada')
            )['t']
            or Decimal('0')
        )
        qrec = rec.quantidade_recebida or Decimal('0')
        if total_aloc > qrec + Decimal('0.01'):
            erros.append(
                f'[{rec.obra_id}] SC {rec.numero_sc}: soma alocações ({total_aloc}) '
                f'maior que quantidade_recebida ({qrec})'
            )

    return erros, avisos


class Command(BaseCommand):
    help = 'Verifica consistência de dados do Mapa de Suprimentos'

    def handle(self, *args, **options):
        erros, avisos = run_verificacao(verbose=True)
        self.stdout.write('VERIFICAÇÃO DO MAPA DE SUPRIMENTOS')
        self.stdout.write(f'Contagens: {len(erros)} erro(s), {len(avisos)} aviso(s)')
        for e in erros:
            self.stdout.write(self.style.ERROR(e))
        for a in avisos:
            self.stdout.write(self.style.WARNING(a))
        if erros:
            self.stderr.write(self.style.ERROR(f'\nTotal: {len(erros)} problema(s) encontrado(s).'))
