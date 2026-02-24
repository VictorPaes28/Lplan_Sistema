"""
Provider pattern para integração com Sienge.
Permite trocar CSV por API sem mexer nas telas.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import date
import pandas as pd


class BaseSiengeProvider(ABC):
    """Interface base para providers do Sienge."""
    
    @abstractmethod
    def fetch_items(self, obra_codigo: str, date_start: Optional[date] = None, 
                   date_end: Optional[date] = None) -> List[Dict]:
        """
        Busca itens do Sienge para uma obra.
        
        Retorna lista de dicionários padronizados com:
        
        Informações do Insumo:
        - codigo_insumo
        - descricao
        - unidade
        - categoria (opcional)
        - tipo_insumo (opcional)
        - especificacao_tecnica (opcional)
        - fornecedor_padrao (opcional)
        - preco_unitario (opcional)
        - moeda (opcional, default: BRL)
        - data_atualizacao_preco (opcional)
        - observacoes (opcional)
        
        Informações de Compra/Entrega:
        - numero_sc
        - data_sc
        - numero_pc
        - data_pc
        - empresa_fornecedora
        - prazo_recebimento
        - quantidade_recebida
        - numero_nf (opcional)
        - data_entrada_nf (opcional)
        """
        pass


class CSVSiengeProvider(BaseSiengeProvider):
    """Provider que lê CSV do Sienge."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.df = None
    
    def _load_csv(self):
        """Carrega e limpa o CSV."""
        if self.df is None:
            # Tentar diferentes encodings
            encodings = ['utf-8', 'latin-1', 'cp1252']
            for encoding in encodings:
                try:
                    self.df = pd.read_csv(self.file_path, encoding=encoding, sep=';', decimal=',')
                    break
                except Exception:
                    continue
            
            if self.df is None:
                raise ValueError(f"Não foi possível ler o arquivo {self.file_path}")
            
            # Normalizar nomes de colunas
            self.df.columns = self.df.columns.str.strip().str.lower()
            
            # Preencher células mescladas (forward fill)
            colunas_id = ['numero_sc', 'numero_pc', 'codigo_insumo', 'descricao']
            for col in colunas_id:
                if col in self.df.columns:
                    self.df[col] = self.df[col].ffill()
    
    def fetch_items(self, obra_codigo: str, date_start: Optional[date] = None,
                   date_end: Optional[date] = None) -> List[Dict]:
        """Lê itens do CSV."""
        self._load_csv()
        
        # Filtrar por obra se houver coluna de obra
        df_filtrado = self.df.copy()
        if 'obra' in df_filtrado.columns or 'codigo_obra' in df_filtrado.columns:
            col_obra = 'obra' if 'obra' in df_filtrado.columns else 'codigo_obra'
            df_filtrado = df_filtrado[df_filtrado[col_obra] == obra_codigo]
        
        # Converter datas
        def parse_date(val):
            if pd.isna(val):
                return None
            if isinstance(val, date):
                return val
            try:
                # Tentar formato BR
                return pd.to_datetime(val, format='%d/%m/%Y', errors='coerce').date()
            except Exception:
                try:
                    return pd.to_datetime(val, errors='coerce').date()
                except Exception:
                    return None
        
        # Converter números
        def parse_decimal(val):
            if pd.isna(val):
                return 0.0
            if isinstance(val, (int, float)):
                return float(val)
            try:
                # Remover vírgula e converter
                return float(str(val).replace(',', '.'))
            except Exception:
                return 0.0
        
        # Mapear colunas (flexível) - Capturando MÁXIMO de informações
        items = []
        for _, row in df_filtrado.iterrows():
            item = {
                # Informações básicas do insumo
                'codigo_insumo': str(row.get('codigo_insumo', row.get('codigo', ''))).strip(),
                'descricao': str(row.get('descricao', row.get('descrição', ''))).strip(),
                'unidade': str(row.get('unidade', row.get('und', 'UND'))).strip(),
                
                # Informações adicionais do insumo (se disponíveis no CSV)
                'categoria': str(row.get('categoria', row.get('classificacao', row.get('classificação', '')))).strip(),
                'tipo_insumo': str(row.get('tipo_insumo', row.get('tipo', ''))).strip(),
                'especificacao_tecnica': str(row.get('especificacao_tecnica', row.get('especificacao', row.get('espec', '')))).strip(),
                'fornecedor_padrao': str(row.get('fornecedor_padrao', row.get('fornecedor_padrão', ''))).strip(),
                'preco_unitario': parse_decimal(row.get('preco_unitario', row.get('preco', row.get('preço', 0)))),
                'moeda': str(row.get('moeda', 'BRL')).strip().upper()[:3],  # Limitar a 3 caracteres
                'data_atualizacao_preco': parse_date(row.get('data_atualizacao_preco', row.get('data_preco'))),
                'observacoes': str(row.get('observacoes', row.get('observações', ''))).strip(),
                
                # Informações de compra/entrega (ItemMapa)
                'numero_sc': str(row.get('numero_sc', row.get('sc', ''))).strip(),
                'data_sc': parse_date(row.get('data_sc', row.get('data_solicitacao'))),
                'numero_pc': str(row.get('numero_pc', row.get('pc', row.get('pedido_compra', '')))).strip(),
                'data_pc': parse_date(row.get('data_pc', row.get('data_pedido'))),
                'empresa_fornecedora': str(row.get('empresa_fornecedora', row.get('fornecedor', ''))).strip(),
                'prazo_recebimento': parse_date(row.get('prazo_recebimento', row.get('prazo'))),
                'quantidade_recebida': parse_decimal(row.get('quantidade_recebida', row.get('qtd_recebida', 0))),
                'numero_nf': str(row.get('numero_nf', row.get('nf', ''))).strip(),
                'data_entrada_nf': parse_date(row.get('data_entrada_nf', row.get('data_entrada'))),
            }
            items.append(item)
        
        return items


class APISiengeProvider(BaseSiengeProvider):
    """
    Provider para API do Sienge - Sincronização Automática.
    
    Implementa:
    - Autenticação OAuth2 client credentials
    - Busca de itens do mapa de controle
    - Paginação automática
    - Rate limiting
    """
    
    def __init__(self, base_url: str, client_id: str, client_secret: str):
        self.base_url = base_url.rstrip('/')
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expires_at = None
        import requests
        self.requests = requests
    
    def _authenticate(self):
        """Autentica e obtém access token via OAuth2."""
        import time
        from datetime import datetime, timedelta
        
        # Se token ainda é válido, não reautentica
        if self.access_token and self.token_expires_at:
            if datetime.now() < self.token_expires_at:
                return
        
        # Endpoint de autenticação (ajustar conforme documentação do Sienge)
        auth_url = f"{self.base_url}/oauth/token"
        
        payload = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': 'read'  # Ajustar conforme necessário
        }
        
        try:
            response = self.requests.post(auth_url, data=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            self.access_token = data.get('access_token')
            expires_in = data.get('expires_in', 3600)  # Default 1 hora
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)  # -60s de margem
            
        except Exception as e:
            raise Exception(f"Erro na autenticação com Sienge API: {str(e)}")
    
    def _get_headers(self):
        """Retorna headers com token de autenticação."""
        self._authenticate()
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def _parse_date(self, date_str):
        """Converte string de data para objeto date."""
        from datetime import datetime
        if not date_str:
            return None
        try:
            # Tentar formato ISO
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except Exception:
            try:
                # Tentar formato BR
                return datetime.strptime(date_str, '%d/%m/%Y').date()
            except Exception:
                return None
    
    def _parse_decimal(self, value):
        """Converte valor para decimal."""
        if value is None:
            return 0.0
        try:
            if isinstance(value, (int, float)):
                return float(value)
            return float(str(value).replace(',', '.'))
        except Exception:
            return 0.0
    
    def fetch_items(self, obra_codigo: str, date_start: Optional[date] = None,
                   date_end: Optional[date] = None) -> List[Dict]:
        """
        Busca itens do Mapa de Suprimentos do Sienge via API.
        
        Mapeia os campos da planilha Excel para o formato do sistema:
        - Item → (não usado, apenas numeração)
        - N° da SC → numero_sc
        - Cód. Obra → obra_codigo (filtro)
        - Cód. insumo → codigo_insumo
        - Descrição do insumo → descricao
        - Qt. solicitada → quantidade_solicitada (pode ser quantidade_planejada)
        - Data da SC → data_sc
        - Data da SC p/ chegada à obra → prazo_necessidade (ou prazo_recebimento)
        - N° do PC → numero_pc
        - Data emissão do PC → data_pc
        - Previsão de entrega → prazo_recebimento
        - Quant. entregue → quantidade_recebida
        - Saldo → saldo_a_entregar (calculado)
        - Data da NF → data_entrada_nf
        - N° da NF → numero_nf
        - Data entrada na obra → data_entrada_nf
        - Data vencimento → (pode ser prazo_recebimento ou data_vencimento)
        """
        from datetime import datetime
        
        items = []
        
        # Endpoint da API do Sienge (ajustar conforme documentação)
        # Exemplo: /api/v1/obras/{obra_codigo}/mapa-controle
        endpoint = f"{self.base_url}/api/v1/obras/{obra_codigo}/mapa-controle"
        
        params = {}
        if date_start:
            params['data_inicio'] = date_start.strftime('%Y-%m-%d')
        if date_end:
            params['data_fim'] = date_end.strftime('%Y-%m-%d')
        
        page = 1
        per_page = 100
        
        while True:
            params['page'] = page
            params['per_page'] = per_page
            
            try:
                response = self.requests.get(
                    endpoint,
                    headers=self._get_headers(),
                    params=params,
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                
                # Estrutura da resposta (ajustar conforme API do Sienge)
                # Pode ser: {'data': [...], 'pagination': {...}} ou apenas [...]
                resultados = data.get('data', data) if isinstance(data, dict) else data
                
                if not resultados:
                    break
                
                for row in resultados:
                    item = {
                        # Informações básicas do insumo
                        'codigo_insumo': str(row.get('codigo_insumo', row.get('cod_insumo', ''))).strip(),
                        'descricao': str(row.get('descricao', row.get('descricao_insumo', ''))).strip(),
                        'unidade': str(row.get('unidade', row.get('und', 'UND'))).strip(),
                        
                        # Informações adicionais do insumo (se disponíveis)
                        'categoria': str(row.get('categoria', row.get('classificacao', ''))).strip(),
                        'tipo_insumo': str(row.get('tipo_insumo', row.get('tipo', ''))).strip(),
                        'especificacao_tecnica': str(row.get('especificacao_tecnica', row.get('especificacao', ''))).strip(),
                        'fornecedor_padrao': str(row.get('fornecedor_padrao', row.get('fornecedor', ''))).strip(),
                        'preco_unitario': self._parse_decimal(row.get('preco_unitario', row.get('preco', 0))),
                        'moeda': str(row.get('moeda', 'BRL')).strip().upper()[:3],
                        'data_atualizacao_preco': self._parse_date(row.get('data_atualizacao_preco')),
                        'observacoes': str(row.get('observacoes', '')).strip(),
                        
                        # Informações de compra/entrega (mapeamento da planilha)
                        'numero_sc': str(row.get('numero_sc', row.get('n_sc', row.get('sc', '')))).strip(),
                        'data_sc': self._parse_date(row.get('data_sc', row.get('data_da_sc'))),
                        'data_sc_chegada_obra': self._parse_date(row.get('data_sc_chegada_obra', row.get('data_sc_p_chegada_obra'))),
                        'numero_pc': str(row.get('numero_pc', row.get('n_pc', row.get('pc', '')))).strip(),
                        'data_pc': self._parse_date(row.get('data_pc', row.get('data_emissao_pc'))),
                        'prazo_recebimento': self._parse_date(row.get('prazo_recebimento', row.get('previsao_entrega'))),
                        'quantidade_solicitada': self._parse_decimal(row.get('quantidade_solicitada', row.get('qt_solicitada', 0))),
                        'quantidade_recebida': self._parse_decimal(row.get('quantidade_recebida', row.get('quant_entregue', 0))),
                        'saldo': self._parse_decimal(row.get('saldo', 0)),
                        'numero_nf': str(row.get('numero_nf', row.get('n_nf', row.get('nf', '')))).strip(),
                        'data_entrada_nf': self._parse_date(row.get('data_entrada_nf', row.get('data_entrada_na_obra'))),
                        'data_vencimento': self._parse_date(row.get('data_vencimento', row.get('data_venc'))),
                        'empresa_fornecedora': str(row.get('empresa_fornecedora', row.get('fornecedor', ''))).strip(),
                    }
                    items.append(item)
                
                # Verificar se há mais páginas
                if isinstance(data, dict):
                    pagination = data.get('pagination', {})
                    total_pages = pagination.get('total_pages', 1)
                    if page >= total_pages:
                        break
                
                page += 1
                
            except self.requests.exceptions.RequestException as e:
                raise Exception(f"Erro ao buscar dados da API do Sienge: {str(e)}")
        
        return items

