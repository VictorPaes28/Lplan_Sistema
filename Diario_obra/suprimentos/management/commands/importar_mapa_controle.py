"""
Comando para importar dados do MAPA_CONTROLE.csv (Sienge) e atualizar RecebimentoObra.

NOVA ARQUITETURA:
- Cria/Atualiza RecebimentoObra (o que CHEGOU na obra, SEM local específico)
- Atualiza campos de referência nos ItemMapa (numero_pc, etc)
- A distribuição para locais é feita MANUALMENTE via AlocacaoRecebimento

SEGREGAÇÃO MULTI-OBRA:
- Se o CSV tiver coluna 'Cód. Obra', usa ela para segregar (recomendado)
- Se não tiver, usa --obra-codigo como fallback
- NUNCA mistura dados de obras diferentes

[!] IMPORTANTE - UNIDADE:
- A unidade de medida (UND, KG, M², etc) NÃO é importada do CSV
- A unidade deve ser definida MANUALMENTE no cadastro do insumo
- O CSV do mapa de controle não traz a unidade de forma confiável

Uso:
    python manage.py importar_mapa_controle --file MAPA_CONTROLE.csv
    python manage.py importar_mapa_controle --file MAPA_CONTROLE.csv --obra-codigo 224
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db import models
from mapa_obras.models import Obra
from suprimentos.models import ItemMapa, RecebimentoObra, Insumo
from decimal import Decimal
from datetime import datetime
import pandas as pd
import os


class Command(BaseCommand):
    help = 'Importa dados do MAPA_CONTROLE.csv (Sienge) e cria/atualiza RecebimentoObra'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Caminho do arquivo MAPA_CONTROLE.csv'
        )
        parser.add_argument(
            '--obra-codigo',
            type=str,
            required=False,
            default=None,
            help='Código da obra no Sienge (fallback se CSV não tiver coluna Cód. Obra)'
        )
        parser.add_argument(
            '--skiprows',
            type=int,
            default=0,
            help='Número de linhas a pular antes do header (padrão: 0)'
        )
        parser.add_argument(
            '--incluir-pequenos',
            action='store_true',
            help='Incluir insumos pequenos e cimentos (padrão: apenas macroelementos entram no mapa)'
        )

    def parse_date(self, val):
        """Converte string de data para objeto date."""
        if pd.isna(val) or not val:
            return None
        if isinstance(val, datetime):
            return val.date()
        try:
            return pd.to_datetime(val, format='%d/%m/%Y', errors='coerce').date()
        except Exception:
            try:
                return pd.to_datetime(val, format='%Y-%m-%d', errors='coerce').date()
            except Exception:
                try:
                    return pd.to_datetime(val, errors='coerce').date()
                except Exception:
                    return None

    def parse_decimal(self, val):
        """Converte valor para Decimal, tratando formato brasileiro (1.000,00)."""
        if pd.isna(val) or val is None:
            return Decimal('0.00')
        
        if isinstance(val, (int, float)):
            return Decimal(str(val))
        
        val_str = str(val).strip()
        if not val_str or val_str == '-':
            return Decimal('0.00')
        
        val_str = val_str.replace(' ', '').replace('R$', '').replace('$', '')
        
        if ',' in val_str and '.' in val_str:
            val_str = val_str.replace('.', '').replace(',', '.')
        elif ',' in val_str:
            val_str = val_str.replace(',', '.')
        
        try:
            return Decimal(val_str)
        except Exception:
            return Decimal('0.00')

    def normalize_column_name(self, col_name):
        """Normaliza nome de coluna para comparação."""
        if pd.isna(col_name):
            return ''
        return str(col_name).strip().upper()

    def handle(self, *args, **options):
        file_path = options['file']
        obra_codigo_fallback = options['obra_codigo']
        skiprows = options['skiprows']
        incluir_pequenos = options.get('incluir_pequenos', False)
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'Arquivo não encontrado: {file_path}'))
            return
        
        self.stdout.write(f'Importando MAPA_CONTROLE.csv para RecebimentoObra...')
        
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
                self.stdout.write(f'   [OK] Arquivo lido com encoding: {encoding}')
                break
            except Exception as e:
                continue
        
        if df is None:
            self.stdout.write(self.style.ERROR('Não foi possível ler o arquivo.'))
            return
        
        df.columns = [self.normalize_column_name(col) for col in df.columns]
        
        # Mapear colunas (ordem de prioridade: variações mais comuns primeiro)
        col_mapping = {
            'item_sc': ['ITEM', 'Nº ITEM', 'N ITEM', 'NUMERO ITEM', 'NÚMERO ITEM', 'N. ITEM'],
            'codigo_obra': ['CÓD. OBRA', 'COD OBRA', 'CODIGO OBRA', 'CODIGO_DA_OBRA', 'COD_OBRA', 'OBRA', 'COD OBRA', 'CÓD OBRA'],
            'codigo_insumo': ['CÓD. INSUMO', 'COD INSUMO', 'CODIGO INSUMO', 'CODIGO_DO_INSUMO', 'COD_INSUMO', 'CÓD INSUMO'],
            'descricao_insumo': ['DESCRIÇÃO DO INSUMO', 'DESCRICAO DO INSUMO', 'DESCRIÇÃO', 'DESCRICAO', 'DESC INSUMO', 'DESCRIÇÃO DO INSUMO', 'DESC. INSUMO'],
            'quantidade_solicitada': ['QT. SOLICITADA', 'QT SOLICITADA', 'QUANTIDADE SOLICITADA', 'QTD SOLICITADA', 'QUANT SOLICITADA', 'QT SOLICITADA'],
            'data_sc': ['DATA DA SC', 'DATA SC', 'DATA_SOLICITACAO', 'DATA SC'],
            'numero_sc': ['Nº DA SC', 'N DA SC', 'NUMERO SC', 'NUMERO_DA_SC', 'SC', 'NSC', 'N. DA SC', 'N. SC'],
            'numero_pc': ['Nº DO PC', 'N DO PC', 'NUMERO PC', 'NUMERO_DO_PC', 'PC', 'NPC', 'N. DO PC', 'N. PC'],
            'previsao_entrega': ['PREVISÃO DE ENTREGA', 'PREVISAO DE ENTREGA', 'PRAZO ENTREGA', 'PRAZO_RECEBIMENTO', 'PREVISÃO ENTREGA'],
            'quantidade_entregue': ['QUANT. ENTREGUE', 'QUANT ENTREGUE', 'QTD ENTREGUE', 'QUANTIDADE ENTREGUE', 'QTD_ENTREGUE', 'QT. ENTREGUE'],
            'saldo': ['SALDO', 'SALDO A ENTREGAR', 'SALDO_A_ENTREGAR', 'SALDO ENTREGAR'],
            'numero_nf': ['Nº DA NF', 'N DA NF', 'NUMERO NF', 'NUMERO_DA_NF', 'NF', 'NNF', 'N. DA NF', 'N. NF'],
            'data_nf': ['DATA DA NF', 'DATA NF', 'DATA_NOTA_FISCAL', 'DATA NF'],
            'data_emissao_pc': ['DATA EMISSÃO DO PC', 'DATA EMISSAO DO PC', 'DATA_PC', 'DATA DO PC', 'DATA EMISSÃO PC'],
            'empresa_fornecedora': ['FORNECEDOR', 'EMPRESA', 'EMPRESA FORNECEDORA', 'RAZAO SOCIAL', 'EMPRESA FORNECEDORA'],
        }
        
        colunas_encontradas = {}
        for campo, possiveis_nomes in col_mapping.items():
            for nome_possivel in possiveis_nomes:
                if nome_possivel in df.columns:
                    colunas_encontradas[campo] = nome_possivel
                    break
        
        if 'numero_sc' not in colunas_encontradas:
            self.stdout.write(self.style.ERROR(
                'Coluna "Nº da SC" não encontrada. Colunas: ' + ', '.join(df.columns.tolist())
            ))
            return
        
        tem_coluna_obra = 'codigo_obra' in colunas_encontradas
        tem_coluna_insumo = 'codigo_insumo' in colunas_encontradas
        
        if tem_coluna_obra:
            self.stdout.write(self.style.SUCCESS(f'   [OK] Coluna "Cód. Obra" encontrada - SEGREGAÇÃO AUTOMÁTICA'))
        else:
            if not obra_codigo_fallback:
                self.stdout.write(self.style.ERROR(
                    'CSV não tem coluna "Cód. Obra" e --obra-codigo não foi fornecido.'
                ))
                return
            self.stdout.write(self.style.WARNING(
                f'   [!] Usando fallback: {obra_codigo_fallback}'
            ))
        
        self.stdout.write(f'   [DATA] Colunas: {", ".join(colunas_encontradas.values())}')
        self.stdout.write(f'   [INFO] Linhas: {len(df)}')
        
        # Caches
        obras_cache = {}
        insumos_cache = {}
        
        def get_obra(codigo):
            codigo_str = str(codigo).strip()
            if codigo_str not in obras_cache:
                try:
                    obras_cache[codigo_str] = Obra.objects.get(codigo_sienge=codigo_str)
                except Obra.DoesNotExist:
                    obras_cache[codigo_str] = None
            return obras_cache[codigo_str]
        
        def get_insumo(codigo):
            # Mantido por compatibilidade interna: agora usamos get_or_create_insumo
            codigo_str = str(codigo).strip()
            if not codigo_str:
                return None
            if codigo_str not in insumos_cache:
                try:
                    insumos_cache[codigo_str] = Insumo.objects.get(codigo_sienge=codigo_str)
                except Insumo.DoesNotExist:
                    insumos_cache[codigo_str] = None
            return insumos_cache[codigo_str]

        def normalizar_desc(desc):
            s = '' if desc is None else str(desc)
            return ' '.join(s.strip().split())

        def get_insumo_ou_none(codigo, descricao):
            """
            Busca insumo existente. NÃO cria automaticamente.
            - Se já existir por código: retorna (atualizando descrição se necessário)
            - Se não existir, tenta "reconciliar" um insumo criado no Levantamento (SM-LEV-*) pelo NOME
            - Se não achar, retorna None (insumo deve ser criado manualmente)
            """
            codigo_str = str(codigo).strip()
            if not codigo_str or codigo_str == 'nan':
                return None

            desc_norm = normalizar_desc(descricao)

            existente = get_insumo(codigo_str)
            if existente:
                # Atualizar descrição se mudou
                if desc_norm and (existente.descricao or '').strip() != desc_norm:
                    existente.descricao = desc_norm[:500]
                    existente.save(update_fields=['descricao', 'updated_at'])
                # Atualizar identificação de macroelemento se necessário
                if desc_norm and desc_norm != existente.descricao:
                    novo_eh_macroelemento = existente.identificar_eh_macroelemento()
                    if novo_eh_macroelemento != existente.eh_macroelemento:
                        existente.eh_macroelemento = novo_eh_macroelemento
                        existente.save(update_fields=['eh_macroelemento', 'updated_at'])
                return existente

            # Reconciliar insumo criado no levantamento (código provisório) pelo nome
            # Isso permite que insumos criados manualmente no levantamento sejam vinculados ao código do Sienge
            if desc_norm:
                candidato = Insumo.objects.filter(
                    descricao__iexact=desc_norm,
                    codigo_sienge__startswith='SM-LEV-'
                ).first()
                if candidato:
                    # Atualizar código provisório para o código real do Sienge
                    candidato.codigo_sienge = codigo_str
                    candidato.descricao = desc_norm[:500]
                    # [!] UNIDADE: Não tentar ler do CSV - deve ser definida manualmente no cadastro do insumo
                    # Se não tiver unidade definida, usar 'UND' apenas como fallback temporário
                    # O usuário deve ajustar manualmente no cadastro do insumo
                    if not candidato.unidade or candidato.unidade.strip() == '':
                        candidato.unidade = 'UND'  # Fallback temporário - ajustar manualmente
                    # Identificar automaticamente se é macroelemento
                    candidato.eh_macroelemento = candidato.identificar_eh_macroelemento()
                    candidato.save()
                    insumos_cache[codigo_str] = candidato
                    return candidato

            # IMPORTANTE: Não criar insumo automaticamente
            # Insumos devem ser criados manualmente antes da importação
            return None
        
        # NOVA LÓGICA: Agrupar por (obra, numero_sc, insumo) e capturar MÁXIMO quantidade_entregue
        # IMPORTANTE: Uma mesma SC pode ter diferentes insumos, então usamos SC + código do insumo como chave
        # A quantidade entregue vem repetida no CSV para o mesmo insumo, então pegamos apenas o maior valor
        grupos_sc = {}  # Chave: (obra, numero_sc, codigo_insumo) -> dados consolidados
        obras_ignoradas = set()
        insumos_nao_encontrados = set()
        
        for idx, row in df.iterrows():
            # Limpar e validar número da SC
            numero_sc_raw = row[colunas_encontradas['numero_sc']]
            numero_sc = str(numero_sc_raw).strip() if pd.notna(numero_sc_raw) else ''
            
            # Remover espaços e caracteres inválidos
            numero_sc = numero_sc.replace(' ', '').replace('.', '').replace('-', '').replace('_', '')
            
            if not numero_sc or numero_sc.lower() == 'nan' or numero_sc == '':
                continue
            
            # Validar que é um número válido (não deve conter apenas texto como "SC")
            if numero_sc.upper() in ('SC', 'NSC', 'NS', 'N', 'NUMERO', 'NUMERO SC'):
                continue
            
            # Código da obra
            if tem_coluna_obra:
                codigo_obra = str(row[colunas_encontradas['codigo_obra']]).strip()
                if not codigo_obra or codigo_obra == 'nan':
                    codigo_obra = obra_codigo_fallback or ''
            else:
                codigo_obra = obra_codigo_fallback or ''
            
            if not codigo_obra:
                continue
            
            obra_obj = get_obra(codigo_obra)
            if not obra_obj:
                obras_ignoradas.add(codigo_obra)
                continue
            
            # Código do insumo - OBRIGATÓRIO para a nova estrutura
            insumo_obj = None
            codigo_insumo = ''
            if tem_coluna_insumo:
                codigo_insumo = str(row[colunas_encontradas['codigo_insumo']]).strip()
                if codigo_insumo and codigo_insumo != 'nan':
                    desc_insumo = ''
                    if 'descricao_insumo' in colunas_encontradas:
                        desc_insumo = row[colunas_encontradas['descricao_insumo']]
                    insumo_obj = get_insumo_ou_none(codigo_insumo, desc_insumo)
                    if not insumo_obj:
                        insumos_nao_encontrados.add(f"{codigo_insumo} ({desc_insumo[:30] if desc_insumo else 'sem descrição'})")
                        continue
            
            if not insumo_obj:
                continue  # Precisa do insumo para criar o recebimento
            
            # FILTRO: Pular insumos pequenos/cimentos se não foi solicitado incluir
            if not incluir_pequenos and not insumo_obj.eh_macroelemento:
                continue  # Não incluir insumos pequenos no mapa de suprimentos
            
            # Chave de agrupamento: (obra, numero_sc, codigo_insumo)
            # IMPORTANTE: Uma mesma SC pode ter diferentes insumos, então cada insumo é tratado separadamente
            # Isso garante que múltiplas linhas do mesmo insumo na mesma SC sejam consolidadas
            chave = (codigo_obra, numero_sc, codigo_insumo)
            
            if chave not in grupos_sc:
                grupos_sc[chave] = {
                    'codigo_obra': codigo_obra,
                    'obra': obra_obj,
                    'insumo': insumo_obj,
                    'numero_sc': numero_sc,
                    'data_sc': None,
                    'numero_pc': '',
                    'previsao_entrega': None,
                    'quantidade_solicitada': Decimal('0.00'),
                    'quantidade_entregue': Decimal('0.00'),  # Será o MÁXIMO encontrado
                    'saldo': Decimal('0.00'),
                    'saldo_arquivo': Decimal('0.00'),
                    'data_emissao_pc': None,
                    'numero_nf': '',
                    'data_nf': None,
                    'empresa_fornecedora': '',
                    'descricao_insumo': '',
                }
            
            # Atualizar descrição se disponível
            if 'descricao_insumo' in colunas_encontradas:
                desc_val = str(row[colunas_encontradas['descricao_insumo']]).strip()
                if desc_val and desc_val != 'nan' and not grupos_sc[chave]['descricao_insumo']:
                    grupos_sc[chave]['descricao_insumo'] = desc_val
            
            # Atualizar data_sc (usar primeira encontrada)
            if 'data_sc' in colunas_encontradas:
                data_sc_val = self.parse_date(row[colunas_encontradas['data_sc']])
                if data_sc_val and not grupos_sc[chave]['data_sc']:
                    grupos_sc[chave]['data_sc'] = data_sc_val
            
            # Atualizar numero_pc (usar primeira encontrada)
            if 'numero_pc' in colunas_encontradas:
                pc_val = str(row[colunas_encontradas['numero_pc']]).strip()
                if pc_val and pc_val != 'nan' and pc_val != '' and not grupos_sc[chave]['numero_pc']:
                    grupos_sc[chave]['numero_pc'] = pc_val
            
            # Atualizar previsao_entrega (usar primeira encontrada)
            if 'previsao_entrega' in colunas_encontradas:
                prazo_val = self.parse_date(row[colunas_encontradas['previsao_entrega']])
                if prazo_val and not grupos_sc[chave]['previsao_entrega']:
                    grupos_sc[chave]['previsao_entrega'] = prazo_val
            
            # IMPORTANTE: Quantidade solicitada - usar primeira encontrada (geralmente é a mesma)
            if 'quantidade_solicitada' in colunas_encontradas:
                qtd_sol = self.parse_decimal(row[colunas_encontradas['quantidade_solicitada']])
                # Debug: logar valores para verificar se está parseando corretamente
                if qtd_sol > Decimal('0.00') and grupos_sc[chave]['quantidade_solicitada'] == Decimal('0.00'):
                    grupos_sc[chave]['quantidade_solicitada'] = qtd_sol
                    # Log para debug (apenas primeira vez que encontra)
                    valor_original = str(row[colunas_encontradas['quantidade_solicitada']])
                    if qtd_sol != Decimal(valor_original.replace(',', '.').replace('.', '', valor_original.count('.') - 1) if '.' in valor_original and ',' in valor_original else valor_original.replace(',', '.')):
                        self.stdout.write(
                            f'   [DATA] [{codigo_obra}] SC {numero_sc}: Quantidade solicitada parseada: "{valor_original}" -> {qtd_sol}'
                        )
            
            # IMPORTANTE: Quantidade entregue - capturar o MÁXIMO (não somar!)
            # PROBLEMA DO SIENGE: O Sienge exporta múltiplas linhas para o mesmo insumo na mesma SC,
            # e cada linha mostra o TOTAL entregue (ex: 4000) repetido em todas as linhas.
            # Exemplo: SC 12345 tem 4 linhas de Cimento, cada uma mostra "4000 entregue",
            # mas 4000 é o total entregue para TODAS as linhas juntas, não 4000 x 4 = 16000.
            # Por isso pegamos apenas o MÁXIMO valor encontrado (que será o mesmo em todas as linhas).
            if 'quantidade_entregue' in colunas_encontradas:
                qtd_val = self.parse_decimal(row[colunas_encontradas['quantidade_entregue']])
                if qtd_val > grupos_sc[chave]['quantidade_entregue']:
                    grupos_sc[chave]['quantidade_entregue'] = qtd_val
            
            # Saldo do arquivo - usar o máximo
            if 'saldo' in colunas_encontradas:
                saldo_val = self.parse_decimal(row[colunas_encontradas['saldo']])
                if saldo_val > grupos_sc[chave]['saldo_arquivo']:
                    grupos_sc[chave]['saldo_arquivo'] = saldo_val
            
            # Data emissão PC (usar primeira encontrada)
            if 'data_emissao_pc' in colunas_encontradas:
                data_pc_val = self.parse_date(row[colunas_encontradas['data_emissao_pc']])
                if data_pc_val and not grupos_sc[chave]['data_emissao_pc']:
                    grupos_sc[chave]['data_emissao_pc'] = data_pc_val
            
            # NF: usar primeira encontrada (geralmente é a mesma para todas as linhas)
            if 'numero_nf' in colunas_encontradas:
                nf_val = str(row[colunas_encontradas['numero_nf']]).strip()
                if nf_val and nf_val != 'nan' and not grupos_sc[chave]['numero_nf']:
                    grupos_sc[chave]['numero_nf'] = nf_val
            
            if 'data_nf' in colunas_encontradas:
                data_nf_val = self.parse_date(row[colunas_encontradas['data_nf']])
                if data_nf_val and not grupos_sc[chave]['data_nf']:
                    grupos_sc[chave]['data_nf'] = data_nf_val
            
            if 'empresa_fornecedora' in colunas_encontradas:
                fornecedor_val = str(row[colunas_encontradas['empresa_fornecedora']]).strip()
                if fornecedor_val and fornecedor_val != 'nan' and not grupos_sc[chave]['empresa_fornecedora']:
                    grupos_sc[chave]['empresa_fornecedora'] = fornecedor_val
        
        if obras_ignoradas:
            self.stdout.write(self.style.WARNING(
                f'   [!] Obras não cadastradas: {", ".join(sorted(obras_ignoradas))}'
            ))
        
        if not incluir_pequenos:
            self.stdout.write(self.style.SUCCESS(
                f'   [OK] Filtro ativo: Apenas macroelementos serão incluídos no mapa'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'   [!] Modo inclusivo: Todos os insumos serão incluídos (incluindo pequenos e cimentos)'
            ))
        
        if insumos_nao_encontrados:
            self.stdout.write(self.style.WARNING(
                f'   [!] Insumos não encontrados (devem ser criados manualmente): {len(insumos_nao_encontrados)} códigos'
            ))
            # Mostrar alguns exemplos
            exemplos = list(insumos_nao_encontrados)[:5]
            for exemplo in exemplos:
                self.stdout.write(self.style.WARNING(f'      - {exemplo}'))
            if len(insumos_nao_encontrados) > 5:
                self.stdout.write(self.style.WARNING(f'      ... e mais {len(insumos_nao_encontrados) - 5} insumo(s)'))
        
        self.stdout.write(f'   [KEY] Grupos únicos processados (obra, SC, código_insumo): {len(grupos_sc)}')
        self.stdout.write(f'   [!] NOTA: Múltiplas linhas do mesmo insumo na mesma SC foram consolidadas.')
        self.stdout.write(f'      A quantidade entregue é o MÁXIMO encontrado (não a soma), pois o Sienge repete o total em todas as linhas.')
        self.stdout.write(f'      Exemplo: SC 12345 pode ter 4 linhas de Cimento (4000 cada) + 1 linha de Tijolo (500).')
        self.stdout.write(f'      Resultado: 1 RecebimentoObra para Cimento (4000) + 1 RecebimentoObra para Tijolo (500).')
        
        # Debug: mostrar algumas linhas processadas
        if len(grupos_sc) > 0:
            exemplos = list(grupos_sc.items())[:3]
            for (cod_obra, sc, cod_ins), dados in exemplos:
                insumo_desc = dados['insumo'].descricao[:40] if dados['insumo'] else 'N/A'
                self.stdout.write(
                    f'   [NOTE] Exemplo: Obra {cod_obra}, SC {sc}, Insumo {cod_ins} ({insumo_desc}) '
                    f'-> Solicitado: {dados["quantidade_solicitada"]}, Entregue (MÁX consolidado): {dados["quantidade_entregue"]}'
                )
        
        # Processar - criar/atualizar RecebimentoObra e atualizar ItemMapa
        total_recebimentos_criados = 0
        total_recebimentos_atualizados = 0
        total_itens_atualizados = 0
        total_itens_nao_encontrados = 0
        erros = []
        obras_processadas = set()
        
        with transaction.atomic():
            # Processar cada grupo (obra, numero_sc, insumo)
            for (codigo_obra, numero_sc, codigo_insumo), dados in grupos_sc.items():
                obra = dados['obra']
                insumo = dados['insumo']
                obras_processadas.add(f"{obra.nome} ({codigo_obra})")

                # Saldo correto: solicitado - entregue (clamp em 0)
                saldo_calc = dados['quantidade_solicitada'] - dados['quantidade_entregue']
                if saldo_calc < 0:
                    saldo_calc = Decimal('0.00')
                # Se quantidades vierem vazias (0/0), usar saldo do arquivo como fallback
                if dados['quantidade_solicitada'] == Decimal('0.00') and dados['quantidade_entregue'] == Decimal('0.00'):
                    saldo_final = max(dados.get('saldo_arquivo', Decimal('0.00')), Decimal('0.00'))
                else:
                    saldo_final = saldo_calc
                
                try:
                    # === 1. CRIAR/ATUALIZAR RecebimentoObra ===
                    # IMPORTANTE: Criar apenas UM RecebimentoObra por (obra, numero_sc, insumo)
                    # Uma mesma SC pode ter diferentes insumos, então cada insumo tem seu próprio RecebimentoObra
                    # Usar item_sc vazio para consolidar, usando a quantidade MÁXIMA entregue
                    # IMPORTANTE: Criar/atualizar SEMPRE que houver quantidade_solicitada > 0
                    # Isso permite calcular o saldo_a_entregar mesmo quando ainda não recebeu nada
                    if insumo and dados['quantidade_solicitada'] > Decimal('0.00'):
                        recebimento, created = RecebimentoObra.objects.update_or_create(
                            obra=obra,
                            numero_sc=numero_sc,
                            insumo=insumo,
                            item_sc='',  # Item_sc vazio para consolidar todas as linhas
                            defaults={
                                'data_sc': dados['data_sc'],
                                'numero_pc': dados['numero_pc'],
                                'data_pc': dados['data_emissao_pc'],
                                'empresa_fornecedora': dados['empresa_fornecedora'],
                                'prazo_recebimento': dados['previsao_entrega'],
                                'descricao_item': (dados.get('descricao_insumo') or '')[:500],
                                'quantidade_solicitada': dados['quantidade_solicitada'],  # Ex: 20000.00 (do CSV)
                                'quantidade_recebida': dados['quantidade_entregue'],  # Pode ser 0 se ainda não chegou
                                'saldo_a_entregar': saldo_final,
                                'numero_nf': dados['numero_nf'],
                                'data_nf': dados['data_nf'],
                            }
                        )
                        
                        if created:
                            total_recebimentos_criados += 1
                        else:
                            total_recebimentos_atualizados += 1
                    
                    # === 2. BUSCAR ItemMapa por numero_sc + insumo e atualizar ===
                    # NOVA LÓGICA: Buscar ItemMapa criado manualmente por (numero_sc + insumo)
                    # IMPORTANTE: Uma mesma SC pode ter diferentes insumos, então buscamos pelo insumo específico
                    # Se encontrar, atualizar status e datas. Se não encontrar, NÃO criar placeholder.
                    # IMPORTANTE: Atualizar ItemMapa sempre que houver quantidade_solicitada > 0
                    # Isso permite mostrar o saldo_a_entregar mesmo quando ainda não recebeu nada
                    # [!] NÃO FAZER ALOCAÇÃO AUTOMÁTICA - apenas armazenar no RecebimentoObra para alocação manual posterior
                    if insumo and numero_sc and dados['quantidade_solicitada'] > Decimal('0.00'):
                        # DEBUG: Verificar quantos ItemMapa existem para este insumo
                        total_itens_insumo = ItemMapa.objects.filter(obra=obra, insumo=insumo).count()
                        self.stdout.write(
                            f'   [SEARCH] [{codigo_obra}] SC {numero_sc}, Insumo {insumo.codigo_sienge} ({insumo.descricao[:40]}): '
                            f'Total de ItemMapa para este insumo: {total_itens_insumo}'
                        )
                        
                        # Buscar ItemMapa criado manualmente para esta SC+Insumo específico
                        # IMPORTANTE: Buscar por insumo (código deve bater) e SC
                        # Excluir apenas placeholders do Sienge (A CLASSIFICAR, sem local, sem criado_por)
                        itens_manuais = list(ItemMapa.objects.filter(
                            obra=obra,
                            insumo=insumo,
                            numero_sc=numero_sc
                        ).exclude(
                            # Excluir apenas placeholders do Sienge
                            models.Q(categoria='A CLASSIFICAR') & 
                            models.Q(local_aplicacao__isnull=True) & 
                            models.Q(criado_por__isnull=True)
                        ))
                        
                        self.stdout.write(
                            f'      -> Busca com SC {numero_sc}: encontrou {len(itens_manuais)} ItemMapa(s)'
                        )
                        
                        # Se não encontrou com SC, buscar sem SC (itens criados manualmente que ainda não têm SC)
                        # Isso permite vincular itens criados manualmente que ainda não têm SC preenchida
                        if not itens_manuais:
                            itens_manuais = list(ItemMapa.objects.filter(
                                obra=obra,
                                insumo=insumo,
                                numero_sc=''  # Sem SC ainda
                            ).exclude(
                                # Excluir apenas placeholders do Sienge
                                models.Q(categoria='A CLASSIFICAR') & 
                                models.Q(local_aplicacao__isnull=True) & 
                                models.Q(criado_por__isnull=True)
                            ))
                            
                            self.stdout.write(
                                f'      -> Busca sem SC: encontrou {len(itens_manuais)} ItemMapa(s)'
                            )
                            
                            # DEBUG: Se ainda não encontrou, listar todos os ItemMapa deste insumo para debug
                            if not itens_manuais:
                                todos_itens_insumo = ItemMapa.objects.filter(obra=obra, insumo=insumo)
                                self.stdout.write(
                                    f'      [!] DEBUG: Listando todos os ItemMapa do insumo {insumo.codigo_sienge}:'
                                )
                                for item_debug in todos_itens_insumo[:5]:  # Mostrar até 5
                                    self.stdout.write(
                                        f'         - ID {item_debug.id}: SC="{item_debug.numero_sc}", '
                                        f'Categoria="{item_debug.categoria}", '
                                        f'Local={item_debug.local_aplicacao_id if item_debug.local_aplicacao else "None"}, '
                                        f'Criado_por={item_debug.criado_por_id if item_debug.criado_por else "None"}'
                                    )
                        
                        # Atualizar TODOS os itens manuais encontrados
                        if itens_manuais:
                            for item_mapa in itens_manuais:
                                # Atualizar com dados do RecebimentoObra
                                if dados['numero_pc'] and dados['numero_pc'] != '':
                                    item_mapa.numero_pc = dados['numero_pc']
                                if dados['data_emissao_pc']:
                                    item_mapa.data_pc = dados['data_emissao_pc']
                                # Sempre atualizar numero_sc se estiver vazio ou diferente
                                if not item_mapa.numero_sc or item_mapa.numero_sc == '':
                                    item_mapa.numero_sc = numero_sc
                                if dados['data_sc']:
                                    item_mapa.data_sc = dados['data_sc']
                                if dados['previsao_entrega']:
                                    item_mapa.prazo_recebimento = dados['previsao_entrega']
                                # Só atualizar empresa_fornecedora se estiver vazio
                                if (not item_mapa.empresa_fornecedora or item_mapa.empresa_fornecedora.strip() == '') and dados['empresa_fornecedora']:
                                    item_mapa.empresa_fornecedora = dados['empresa_fornecedora']
                                
                                # Limpar item_sc para permitir vinculação com RecebimentoObra
                                if item_mapa.item_sc:
                                    item_mapa.item_sc = ''
                                
                                # Atualizar quantidade_recebida e saldo_a_entregar a partir do RecebimentoObra
                                # [!] IMPORTANTE: NÃO criar AlocacaoRecebimento aqui - apenas atualizar referências
                                # A alocação será feita MANUALMENTE pelo usuário quando ele clicar no botão de alocar
                                recebimento = RecebimentoObra.objects.filter(
                                    obra=obra,
                                    numero_sc=numero_sc,
                                    insumo=insumo,
                                    item_sc=''
                                ).first()
                                
                                if recebimento:
                                    # Apenas atualizar campos de referência - NÃO alocar automaticamente
                                    item_mapa.quantidade_recebida = recebimento.quantidade_recebida
                                    item_mapa.saldo_a_entregar = recebimento.saldo_a_entregar_calculado
                                
                                item_mapa.save()
                                total_itens_atualizados += 1
                            
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'   [OK] [{codigo_obra}] SC {numero_sc}, Insumo {insumo.codigo_sienge} ({insumo.descricao[:40]}): '
                                    f'{len(itens_manuais)} ItemMapa(s) atualizado(s)'
                                )
                            )
                        else:
                            # Item não encontrado - não criar placeholder
                            total_itens_nao_encontrados += 1
                            self.stdout.write(
                                self.style.WARNING(
                                    f'   [!] [{codigo_obra}] SC {numero_sc}, Insumo {insumo.codigo_sienge} ({insumo.descricao[:40]}): '
                                    f'ItemMapa não encontrado (não será criado automaticamente)'
                                )
                            )
                
                except Exception as e:
                    erro_msg = f"Erro [{codigo_obra}] SC {numero_sc}: {str(e)}"
                    erros.append(erro_msg)
                    self.stdout.write(self.style.ERROR(f'   [ERR] {erro_msg}'))
        
        # Resumo
        self.stdout.write(self.style.SUCCESS(
            f'\n[OK] Importação concluída:\n'
            f'   [PKG] Obras: {", ".join(sorted(obras_processadas))}\n'
            f'   [NEW] RecebimentoObra criados: {total_recebimentos_criados}\n'
            f'   [UPD] RecebimentoObra atualizados: {total_recebimentos_atualizados}\n'
            f'   [INFO] ItemMapa atualizados: {total_itens_atualizados}\n'
            f'   [SKIP] SC sem ItemMapa encontrado: {total_itens_nao_encontrados}'
        ))
        
        if total_itens_nao_encontrados > 0:
            self.stdout.write(self.style.WARNING(
                f'\n[TIP] DICA: {total_itens_nao_encontrados} SC(s) não foram encontradas no Mapa (ItemMapa).\n'
                f'   Os dados estão no RecebimentoObra e serão vinculados quando a Engenharia criar os itens manualmente no Levantamento.'
            ))
        
        if erros:
            self.stdout.write(self.style.WARNING(f'\n[!] {len(erros)} erros:'))
            for erro in erros[:10]:
                self.stdout.write(self.style.WARNING(f'   - {erro}'))
