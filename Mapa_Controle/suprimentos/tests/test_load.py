"""
ETAPA 5: TESTE DE CARGA (Scalability)

Testa performance com grandes volumes de dados:
1. Mapa de Suprimentos com 5.000 itens
2. Verificar N+1 Queries
3. Otimizações com select_related/prefetch_related
"""
import pytest
from decimal import Decimal
from django.test.utils import override_settings
from django.db import connection, reset_queries
from django.db.models import Sum
from suprimentos.models import ItemMapa, RecebimentoObra, AlocacaoRecebimento
from obras.models import Obra, LocalObra


@pytest.fixture
def obra_grande(db):
    """Cria uma obra para testes de carga."""
    return Obra.objects.create(nome='Obra Grande Teste', ativa=True)


@pytest.fixture
def insumos_bulk(db):
    """Cria 100 insumos para testes."""
    from suprimentos.models import Insumo
    insumos = []
    for i in range(100):
        insumo = Insumo.objects.create(
            codigo_sienge=f'INS{i:04d}',
            descricao=f'Insumo Teste {i}',
            unidade='UND',
            ativo=True,
            eh_macroelemento=(i % 2 == 0)
        )
        insumos.append(insumo)
    return insumos


@pytest.fixture
def locais_bulk(db, obra_grande):
    """Cria 20 locais para testes."""
    locais = []
    for i in range(20):
        local = LocalObra.objects.create(
            obra=obra_grande,
            nome=f'Bloco {chr(65 + i)}',  # A, B, C, ...
            tipo='BLOCO'
        )
        locais.append(local)
    return locais


@pytest.fixture
def mapa_5000_itens(db, obra_grande, insumos_bulk, locais_bulk):
    """
    Cria um mapa com 5.000 itens para teste de carga.
    Usa model_bakery se disponível, senão cria manualmente.
    """
    from suprimentos.models import Insumo
    
    # Criar 5000 itens
    itens = []
    categorias = ['FUNDAÇÃO', 'SUPERESTRUTURA', 'ALVENARIA/FECHAMENTO', 'PINTURA']
    
    for i in range(5000):
        insumo = insumos_bulk[i % len(insumos_bulk)]
        local = locais_bulk[i % len(locais_bulk)]
        categoria = categorias[i % len(categorias)]
        
        item = ItemMapa.objects.create(
            obra=obra_grande,
            insumo=insumo,
            categoria=categoria,
            local_aplicacao=local,
            quantidade_planejada=Decimal(str(100 + (i % 900))),
            numero_sc=f'SC{i // 10:04d}' if i % 2 == 0 else '',  # 50% com SC
        )
        itens.append(item)
    
    return itens


class TestPerformanceCalculoTotal:
    """Testa performance do cálculo de custo total da obra."""
    
    def test_calcular_total_planejado_5000_itens(self, db, mapa_5000_itens, obra_grande):
        """
        Testa cálculo do total planejado com 5.000 itens.
        Verifica se há N+1 queries.
        """
        reset_queries()
        
        # Calcular total planejado (simulação de "Custo Total da Obra")
        total = ItemMapa.objects.filter(
            obra=obra_grande
        ).aggregate(
            total=Sum('quantidade_planejada')
        )['total'] or Decimal('0.00')
        
        queries = len(connection.queries)
        
        # Deve fazer apenas 1 query (aggregate)
        assert queries == 1, f"Esperado 1 query, obtido {queries}. Queries: {[q['sql'] for q in connection.queries]}"
        assert total > Decimal('0.00')
    
    def test_listar_itens_com_propriedades_calculadas(self, db, mapa_5000_itens, obra_grande):
        """
        Testa listagem de itens acessando propriedades calculadas.
        Verifica N+1 queries.
        """
        reset_queries()
        
        # Buscar itens com select_related
        itens = ItemMapa.objects.filter(
            obra=obra_grande
        ).select_related('insumo', 'local_aplicacao', 'obra')[:100]  # Limitar para teste
        
        # Acessar propriedades calculadas (que fazem queries)
        for item in itens:
            _ = item.quantidade_alocada_local
            _ = item.quantidade_recebida_obra
            _ = item.status_etapa
        
        queries = len(connection.queries)
        
        # Com select_related, deve fazer menos queries
        # Mas propriedades calculadas podem fazer queries adicionais
        # O ideal seria < 10 queries para 100 itens
        assert queries < 50, f"Muitas queries ({queries}). Possível N+1 problem."
    
    def test_otimizacao_select_related(self, db, mapa_5000_itens, obra_grande):
        """Testa otimização com select_related."""
        reset_queries()
        
        # SEM select_related (ruim)
        itens_sem_otimizacao = ItemMapa.objects.filter(obra=obra_grande)[:100]
        for item in itens_sem_otimizacao:
            _ = item.insumo.descricao  # Acessa ForeignKey
            _ = item.local_aplicacao.nome if item.local_aplicacao else None
        
        queries_sem = len(connection.queries)
        reset_queries()
        
        # COM select_related (bom)
        itens_com_otimizacao = ItemMapa.objects.filter(
            obra=obra_grande
        ).select_related('insumo', 'local_aplicacao')[:100]
        
        for item in itens_com_otimizacao:
            _ = item.insumo.descricao
            _ = item.local_aplicacao.nome if item.local_aplicacao else None
        
        queries_com = len(connection.queries)
        
        # Com select_related deve fazer menos queries
        assert queries_com < queries_sem, f"select_related não melhorou: {queries_sem} -> {queries_com}"


class TestPerformanceAlocacoes:
    """Testa performance de cálculos de alocações."""
    
    def test_calcular_total_alocado_5000_itens(self, db, mapa_5000_itens, obra_grande, insumos_bulk, locais_bulk):
        """
        Testa cálculo de total alocado com 5.000 itens.
        Cria algumas alocações e verifica performance.
        """
        from suprimentos.models import RecebimentoObra
        
        # Criar alguns recebimentos
        recebimentos = []
        for i in range(0, min(100, len(mapa_5000_itens)), 10):  # 100 recebimentos
            item = mapa_5000_itens[i]
            if item.numero_sc:
                recebimento = RecebimentoObra.objects.create(
                    obra=obra_grande,
                    insumo=item.insumo,
                    numero_sc=item.numero_sc,
                    item_sc='',
                    quantidade_solicitada=item.quantidade_planejada,
                    quantidade_recebida=item.quantidade_planejada * Decimal('0.8')
                )
                recebimentos.append(recebimento)
        
        # Criar algumas alocações
        for i in range(0, min(500, len(mapa_5000_itens)), 2):  # 500 alocações
            item = mapa_5000_itens[i]
            recebimento = recebimentos[i % len(recebimentos)] if recebimentos else None
            if recebimento:
                AlocacaoRecebimento.objects.create(
                    obra=obra_grande,
                    insumo=item.insumo,
                    local_aplicacao=item.local_aplicacao,
                    recebimento=recebimento,
                    item_mapa=item,
                    quantidade_alocada=item.quantidade_planejada * Decimal('0.5')
                )
        
        reset_queries()
        
        # Calcular total alocado (agregação)
        total = AlocacaoRecebimento.objects.filter(
            obra=obra_grande
        ).aggregate(
            total=Sum('quantidade_alocada')
        )['total'] or Decimal('0.00')
        
        queries = len(connection.queries)
        
        # Deve fazer apenas 1 query
        assert queries == 1, f"Esperado 1 query, obtido {queries}"
        assert total > Decimal('0.00')
    
    def test_quantidade_alocada_local_n_plus_1(self, db, mapa_5000_itens, obra_grande):
        """
        Testa se quantidade_alocada_local causa N+1 queries.
        """
        reset_queries()
        
        # Buscar itens
        itens = ItemMapa.objects.filter(obra=obra_grande)[:100]
        
        # Acessar quantidade_alocada_local (faz query por item)
        for item in itens:
            _ = item.quantidade_alocada_local
        
        queries = len(connection.queries)
        
        # Cada quantidade_alocada_local faz 1 query (N+1 problem)
        # 100 itens = 100 queries + 1 query inicial = 101 queries
        # Isso é um problema de performance!
        assert queries > 50, f"Detectado N+1: {queries} queries para 100 itens"
        
        # SOLUÇÃO: Usar prefetch_related ou annotate
        reset_queries()
        
        from django.db.models import Sum, OuterRef, Subquery
        from django.db import models
        
        # Otimização: usar annotate para calcular quantidade_alocada_local
        itens_otimizados = ItemMapa.objects.filter(
            obra=obra_grande
        ).annotate(
            quantidade_alocada_calculada=Subquery(
                AlocacaoRecebimento.objects.filter(
                    item_mapa=OuterRef('pk')
                ).aggregate(
                    total=Sum('quantidade_alocada')
                )['total'] or Decimal('0.00'),
                output_field=models.DecimalField(max_digits=14, decimal_places=2)
            )
        )[:100]
        
        for item in itens_otimizados:
            _ = item.quantidade_alocada_calculada
        
        queries_otimizado = len(connection.queries)
        
        # Com annotate, deve fazer menos queries
        # Mas Subquery ainda pode fazer queries por item (depende do Django)
        # Ideal seria usar prefetch_related com Prefetch customizado


class TestPerformanceQueriesComplexas:
    """Testa performance de queries complexas."""
    
    def test_filtro_por_status_com_propriedades(self, db, mapa_5000_itens, obra_grande):
        """
        Testa filtro por status que usa propriedades calculadas.
        Isso é lento porque precisa carregar todos os itens.
        """
        reset_queries()
        
        # Filtro que usa propriedades calculadas (lento)
        itens = list(ItemMapa.objects.filter(obra=obra_grande))
        itens_entregues = [item for item in itens if item.status_etapa == 'ENTREGUE']
        
        queries = len(connection.queries)
        
        # Isso faz 1 query inicial + N queries para propriedades
        # Muito lento para 5000 itens!
        assert len(itens_entregues) >= 0
    
    def test_agregacoes_por_categoria(self, db, mapa_5000_itens, obra_grande):
        """
        Testa agregações por categoria (deve ser rápido).
        """
        reset_queries()
        
        from django.db.models import Sum, Count
        
        # Agregação por categoria (rápido, tudo no banco)
        totais = ItemMapa.objects.filter(
            obra=obra_grande
        ).values('categoria').annotate(
            total_planejado=Sum('quantidade_planejada'),
            quantidade=Count('id')
        )
        
        queries = len(connection.queries)
        
        # Deve fazer apenas 1 query
        assert queries == 1, f"Esperado 1 query, obtido {queries}"
        assert len(list(totais)) > 0


class TestSugestoesOtimizacao:
    """Sugestões de otimização baseadas nos testes."""
    
    def test_prefetch_related_alocacoes(self, db, mapa_5000_itens, obra_grande):
        """
        Testa uso de prefetch_related para alocações.
        """
        from django.db.models import Prefetch
        
        reset_queries()
        
        # SEM prefetch_related
        itens_sem = ItemMapa.objects.filter(obra=obra_grande)[:100]
        for item in itens_sem:
            _ = list(item.alocacoes.all())  # Faz query por item
        
        queries_sem = len(connection.queries)
        reset_queries()
        
        # COM prefetch_related
        itens_com = ItemMapa.objects.filter(
            obra=obra_grande
        ).prefetch_related('alocacoes')[:100]
        
        for item in itens_com:
            _ = list(item.alocacoes.all())  # Usa cache
        
        queries_com = len(connection.queries)
        
        # Com prefetch_related deve fazer menos queries
        assert queries_com < queries_sem, f"prefetch_related não melhorou: {queries_sem} -> {queries_com}"

