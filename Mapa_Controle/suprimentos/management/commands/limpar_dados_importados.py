"""
Comando para limpar dados importados do Sienge, mantendo estrutura básica.

Remove:
- RecebimentoObra (dados importados)
- AlocacaoRecebimento (alocações manuais)
- ItemMapa criados pela importação (placeholders)
- NotaFiscalEntrada
- HistoricoAlteracao relacionado

Mantém:
- Usuários
- Obras
- Locais
- Insumos
- ItemMapa criados manualmente (com criado_por)

Uso:
    python manage.py limpar_dados_importados
    python manage.py limpar_dados_importados --confirmar
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from suprimentos.models import (
    RecebimentoObra, 
    AlocacaoRecebimento, 
    ItemMapa, 
    NotaFiscalEntrada,
    HistoricoAlteracao
)


class Command(BaseCommand):
    help = 'Limpa dados importados do Sienge, mantendo estrutura básica (usuários, obras, insumos)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirma a limpeza (sem isso, apenas mostra o que será removido)'
        )

    def handle(self, *args, **options):
        confirmar = options.get('confirmar', False)
        
        if not confirmar:
            self.stdout.write(self.style.WARNING(
                '\n⚠️  MODO SIMULAÇÃO - Nada será removido ainda.\n'
                'Use --confirmar para realmente limpar os dados.\n'
            ))
        
        # Contar o que será removido
        total_recebimentos = RecebimentoObra.objects.count()
        total_alocacoes = AlocacaoRecebimento.objects.count()
        
        # ItemMapa criados pela importação (placeholders)
        # Placeholders: categoria='A CLASSIFICAR', sem local, sem criado_por
        placeholders = ItemMapa.objects.filter(
            categoria='A CLASSIFICAR',
            local_aplicacao__isnull=True,
            criado_por__isnull=True
        )
        total_placeholders = placeholders.count()
        
        # ItemMapa criados manualmente (manter)
        itens_manuais = ItemMapa.objects.exclude(
            Q(categoria='A CLASSIFICAR') & 
            Q(local_aplicacao__isnull=True) & 
            Q(criado_por__isnull=True)
        )
        total_itens_manuais = itens_manuais.count()
        
        total_notas = NotaFiscalEntrada.objects.count()
        
        # Histórico relacionado aos dados que serão removidos
        historico_remover = HistoricoAlteracao.objects.filter(
            Q(item_mapa__in=placeholders) | 
            Q(tipo='IMPORTACAO')
        )
        total_historico = historico_remover.count()
        
        # Mostrar resumo
        self.stdout.write(self.style.SUCCESS('\n📊 RESUMO DO QUE SERÁ REMOVIDO:\n'))
        self.stdout.write(f'   🗑️  RecebimentoObra: {total_recebimentos}')
        self.stdout.write(f'   🗑️  AlocacaoRecebimento: {total_alocacoes}')
        self.stdout.write(f'   🗑️  ItemMapa (placeholders): {total_placeholders}')
        self.stdout.write(f'   🗑️  NotaFiscalEntrada: {total_notas}')
        self.stdout.write(f'   🗑️  HistoricoAlteracao: {total_historico}')
        
        self.stdout.write(self.style.SUCCESS('\n✅ O QUE SERÁ MANTIDO:\n'))
        self.stdout.write(f'   ✅ Usuários: mantidos')
        self.stdout.write(f'   ✅ Obras: mantidas')
        self.stdout.write(f'   ✅ Locais: mantidos')
        self.stdout.write(f'   ✅ Insumos: mantidos')
        self.stdout.write(f'   ✅ ItemMapa criados manualmente: {total_itens_manuais} (mantidos)')
        
        if not confirmar:
            self.stdout.write(self.style.WARNING(
                '\n💡 Para realmente limpar, execute:\n'
                '   python manage.py limpar_dados_importados --confirmar\n'
            ))
            return
        
        # Confirmar limpeza
        self.stdout.write(self.style.WARNING('\n🗑️  INICIANDO LIMPEZA...\n'))
        
        with transaction.atomic():
            # 1. Remover alocações primeiro (dependem de recebimentos)
            if total_alocacoes > 0:
                self.stdout.write(f'   Removendo {total_alocacoes} AlocacaoRecebimento...')
                AlocacaoRecebimento.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'      ✅ {total_alocacoes} removidos'))
            
            # 2. Remover notas fiscais
            if total_notas > 0:
                self.stdout.write(f'   Removendo {total_notas} NotaFiscalEntrada...')
                NotaFiscalEntrada.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'      ✅ {total_notas} removidas'))
            
            # 3. Remover recebimentos
            if total_recebimentos > 0:
                self.stdout.write(f'   Removendo {total_recebimentos} RecebimentoObra...')
                RecebimentoObra.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'      ✅ {total_recebimentos} removidos'))
            
            # 4. Remover placeholders (ItemMapa criados pela importação)
            if total_placeholders > 0:
                self.stdout.write(f'   Removendo {total_placeholders} ItemMapa (placeholders)...')
                placeholders.delete()
                self.stdout.write(self.style.SUCCESS(f'      ✅ {total_placeholders} removidos'))
            
            # 5. Remover histórico relacionado
            if total_historico > 0:
                self.stdout.write(f'   Removendo {total_historico} HistoricoAlteracao...')
                historico_remover.delete()
                self.stdout.write(self.style.SUCCESS(f'      ✅ {total_historico} removidos'))
            
            # 6. Limpar campos de referência nos ItemMapa manuais
            itens_para_limpar = ItemMapa.objects.filter(
                Q(numero_sc__isnull=False) & ~Q(numero_sc='')
            ).exclude(
                Q(categoria='A CLASSIFICAR') & 
                Q(local_aplicacao__isnull=True) & 
                Q(criado_por__isnull=True)
            )
            
            total_limpar_campos = itens_para_limpar.count()
            if total_limpar_campos > 0:
                self.stdout.write(f'   Limpando campos de referência em {total_limpar_campos} ItemMapa manuais...')
                itens_para_limpar.update(
                    numero_sc='',
                    item_sc='',
                    data_sc=None,
                    numero_pc='',
                    data_pc=None,
                    empresa_fornecedora='',
                    prazo_recebimento=None,
                    quantidade_recebida=0,
                    saldo_a_entregar=0,
                    status_sienge_raw=''
                )
                self.stdout.write(self.style.SUCCESS(f'      ✅ {total_limpar_campos} atualizados'))
        
        self.stdout.write(self.style.SUCCESS(
            '\n✅ Limpeza concluída com sucesso!\n'
            '   Estrutura básica (usuários, obras, insumos, ItemMapa manuais) foi mantida.\n'
        ))

