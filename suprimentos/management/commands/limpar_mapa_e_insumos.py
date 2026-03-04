"""
Comando para apagar todos os dados do mapa de suprimentos e todos os insumos.

Remove (nesta ordem, por dependências de FK):
- AlocacaoRecebimento
- NotaFiscalEntrada
- HistoricoAlteracao
- ItemMapa (todos os itens do mapa)
- RecebimentoObra (dados importados do Sienge)
- Insumo (catálogo de insumos)

Mantém: usuários, obras, locais (mapa_obras).

Uso:
    python manage.py limpar_mapa_e_insumos
    python manage.py limpar_mapa_e_insumos --confirmar
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from suprimentos.models import (
    AlocacaoRecebimento,
    NotaFiscalEntrada,
    HistoricoAlteracao,
    ItemMapa,
    RecebimentoObra,
    Insumo,
)


class Command(BaseCommand):
    help = 'Apaga todos os dados do mapa de suprimentos e todos os insumos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirma a exclusão (sem isso, apenas mostra o que será removido)',
        )

    def handle(self, *args, **options):
        confirmar = options.get('confirmar', False)

        if not confirmar:
            self.stdout.write(self.style.WARNING(
                '\nMODO SIMULACAO - Nada sera removido.\n'
                'Use --confirmar para realmente apagar.\n'
            ))

        n_aloc = AlocacaoRecebimento.objects.count()
        n_nf = NotaFiscalEntrada.objects.count()
        n_hist = HistoricoAlteracao.objects.count()
        n_itens = ItemMapa.objects.count()
        n_receb = RecebimentoObra.objects.count()
        n_insumos = Insumo.objects.count()

        self.stdout.write(self.style.SUCCESS('\nO QUE SERA REMOVIDO:\n'))
        self.stdout.write(f'   AlocacaoRecebimento: {n_aloc}')
        self.stdout.write(f'   NotaFiscalEntrada: {n_nf}')
        self.stdout.write(f'   HistoricoAlteracao: {n_hist}')
        self.stdout.write(f'   ItemMapa (mapa de suprimentos): {n_itens}')
        self.stdout.write(f'   RecebimentoObra: {n_receb}')
        self.stdout.write(f'   Insumo: {n_insumos}')

        if not confirmar:
            self.stdout.write(self.style.WARNING(
                '\nPara executar a exclusao:\n'
                '   python manage.py limpar_mapa_e_insumos --confirmar\n'
            ))
            return

        self.stdout.write(self.style.WARNING('\nApagando...\n'))

        with transaction.atomic():
            AlocacaoRecebimento.objects.all().delete()
            self.stdout.write('   OK AlocacaoRecebimento')
            NotaFiscalEntrada.objects.all().delete()
            self.stdout.write('   OK NotaFiscalEntrada')
            HistoricoAlteracao.objects.all().delete()
            self.stdout.write('   OK HistoricoAlteracao')
            ItemMapa.objects.all().delete()
            self.stdout.write('   OK ItemMapa')
            RecebimentoObra.objects.all().delete()
            self.stdout.write('   OK RecebimentoObra')
            Insumo.objects.all().delete()
            self.stdout.write('   OK Insumo')

        self.stdout.write(self.style.SUCCESS('\nMapa de suprimentos e insumos apagados.\n'))
