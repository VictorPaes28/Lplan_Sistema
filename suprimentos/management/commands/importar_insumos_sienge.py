"""
Comando para importar o catálogo de INSUMOS do CSV do Sienge.

Lê o CSV do MAPA_CONTROLE e extrai os insumos únicos (código + descrição).
Cria ou atualiza o catálogo de insumos no banco.

Uso:
    python manage.py importar_insumos_sienge --file MAPA_CONTROLE.csv
    python manage.py importar_insumos_sienge --file MAPA_CONTROLE.csv --atualizar-descricao
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from suprimentos.models import Insumo
import pandas as pd
import os


class Command(BaseCommand):
    help = 'Importa catálogo de insumos do CSV do Sienge (extrai códigos e descrições únicos)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Caminho do arquivo CSV (MAPA_CONTROLE.csv)'
        )
        parser.add_argument(
            '--atualizar-descricao',
            action='store_true',
            help='Atualiza descrição de insumos já existentes'
        )
        parser.add_argument(
            '--skiprows',
            type=int,
            default=0,
            help='Número de linhas a pular antes do header (padrão: 0)'
        )

    def normalize_column_name(self, col_name):
        """Normaliza nome de coluna para comparação."""
        if pd.isna(col_name):
            return ''
        return str(col_name).strip().upper()

    def handle(self, *args, **options):
        file_path = options['file']
        atualizar_descricao = options['atualizar_descricao']
        skiprows = options['skiprows']
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'Arquivo não encontrado: {file_path}'))
            return
        
        self.stdout.write(f'📦 Importando catálogo de INSUMOS do Sienge...')
        
        # Ler CSV
        df = None
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                df = pd.read_csv(
                    file_path,
                    encoding=encoding,
                    sep=';',
                    decimal=',',
                    skiprows=skiprows,
                    dtype=str,
                    na_values=['', ' ', '-', 'N/A', 'n/a']
                )
                self.stdout.write(f'   ✅ Arquivo lido com encoding: {encoding}')
                break
            except Exception as e:
                continue
        
        if df is None:
            self.stdout.write(self.style.ERROR('Não foi possível ler o arquivo.'))
            return
        
        # Normalizar nomes de colunas
        df.columns = [self.normalize_column_name(col) for col in df.columns]
        
        # Mapear colunas
        col_mapping = {
            'codigo_insumo': ['CÓD. INSUMO', 'COD INSUMO', 'CODIGO INSUMO', 'CODIGO_DO_INSUMO', 'COD_INSUMO', 'CÓDIGO INSUMO'],
            'descricao_insumo': ['DESCRIÇÃO DO INSUMO', 'DESCRICAO DO INSUMO', 'DESCRIÇÃO', 'DESCRICAO', 'DESC INSUMO', 'DESCRIÇÃO INSUMO'],
            'unidade': ['UNIDADE', 'UND', 'UN', 'UNID', 'UNIDADE DE MEDIDA'],
        }
        
        colunas_encontradas = {}
        for campo, possiveis_nomes in col_mapping.items():
            for nome_possivel in possiveis_nomes:
                if nome_possivel in df.columns:
                    colunas_encontradas[campo] = nome_possivel
                    break
        
        # Validar colunas obrigatórias
        if 'codigo_insumo' not in colunas_encontradas:
            self.stdout.write(self.style.ERROR(
                'Coluna "Cód. insumo" não encontrada.\n'
                f'Colunas disponíveis: {", ".join(df.columns.tolist())}'
            ))
            return
        
        if 'descricao_insumo' not in colunas_encontradas:
            self.stdout.write(self.style.ERROR(
                'Coluna "Descrição do insumo" não encontrada.\n'
                f'Colunas disponíveis: {", ".join(df.columns.tolist())}'
            ))
            return
        
        tem_unidade = 'unidade' in colunas_encontradas
        
        self.stdout.write(f'   📊 Colunas encontradas: {", ".join(colunas_encontradas.values())}')
        if not tem_unidade:
            self.stdout.write(self.style.WARNING('   ⚠️ Coluna "Unidade" não encontrada - usando "UND" como padrão'))
        
        # Extrair insumos únicos
        insumos_unicos = {}
        
        for idx, row in df.iterrows():
            codigo = str(row[colunas_encontradas['codigo_insumo']]).strip()
            descricao = str(row[colunas_encontradas['descricao_insumo']]).strip()
            
            if not codigo or codigo == 'nan' or not descricao or descricao == 'nan':
                continue
            
            # Pegar unidade se existir
            unidade = 'UND'
            if tem_unidade:
                unid_val = str(row[colunas_encontradas['unidade']]).strip()
                if unid_val and unid_val != 'nan':
                    unidade = unid_val.upper()
            
            # Guardar (primeiro encontrado, ou atualiza se descrição maior/melhor)
            if codigo not in insumos_unicos:
                insumos_unicos[codigo] = {
                    'descricao': descricao,
                    'unidade': unidade
                }
            else:
                # Se a nova descrição for mais completa, usa ela
                if len(descricao) > len(insumos_unicos[codigo]['descricao']):
                    insumos_unicos[codigo]['descricao'] = descricao
        
        self.stdout.write(f'   🔑 Insumos únicos encontrados: {len(insumos_unicos)}')
        
        # Importar para o banco
        total_criados = 0
        total_atualizados = 0
        total_ignorados = 0
        
        with transaction.atomic():
            for codigo, dados in insumos_unicos.items():
                try:
                    insumo, created = Insumo.objects.get_or_create(
                        codigo_sienge=codigo,
                        defaults={
                            'descricao': dados['descricao'],
                            'unidade': dados['unidade'],
                            'ativo': True
                        }
                    )
                    
                    if created:
                        total_criados += 1
                        self.stdout.write(f'   ✅ CRIADO: {codigo} - {dados["descricao"][:50]}...')
                    else:
                        # Já existe
                        if atualizar_descricao:
                            insumo.descricao = dados['descricao']
                            insumo.unidade = dados['unidade']
                            insumo.save()
                            total_atualizados += 1
                            self.stdout.write(f'   🔄 ATUALIZADO: {codigo}')
                        else:
                            total_ignorados += 1
                
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'   ❌ Erro em {codigo}: {str(e)}'))
        
        # Resumo
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Importação de insumos concluída:\n'
            f'   🆕 Criados: {total_criados}\n'
            f'   🔄 Atualizados: {total_atualizados}\n'
            f'   ⏭️ Já existiam (ignorados): {total_ignorados}\n'
            f'   📦 Total no catálogo: {Insumo.objects.count()}'
        ))
        
        if total_ignorados > 0 and not atualizar_descricao:
            self.stdout.write(self.style.WARNING(
                '\n💡 DICA: Use --atualizar-descricao para atualizar insumos existentes.'
            ))

