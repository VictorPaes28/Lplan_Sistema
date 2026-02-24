"""
ETAPA 2: TESTES UNITÁRIOS DE MATEMÁTICA (O "Pente Fino")

Testes que cobrem:
1. O Teste do Centavo: arredondamento financeiro vs matemático
2. Divisão por Zero: tratamento de erros
3. Valores Negativos: validação de entrada
4. Conversão de Unidade: precisão de cálculos
"""
import pytest
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from django.core.exceptions import ValidationError
from suprimentos.models import ItemMapa, RecebimentoObra, AlocacaoRecebimento, Insumo
from mapa_obras.models import Obra, LocalObra


class TestCentavo:
    """1. O Teste do Centavo: Cálculos com valores fracionários."""
    
    def test_preco_unitario_0_33_quantidade_3(self, db, obra, insumo, local_obra):
        """
        Cenário: Preço unitário 0.33, quantidade 3.
        Total deve ser 0.99 (não 1.00 por arredondamento).
        """
        # Nota: O sistema não tem campo de preço, mas testamos a precisão Decimal
        qtd1 = Decimal('0.33')
        qtd2 = Decimal('0.33')
        qtd3 = Decimal('0.33')
        total = qtd1 + qtd2 + qtd3
        
        # Deve ser exatamente 0.99, não 1.00
        assert total == Decimal('0.99'), f"Esperado 0.99, obtido {total}"
        
        # Teste prático: alocação com valores fracionários
        recebimento = RecebimentoObra.objects.create(
            obra=obra,
            insumo=insumo,
            numero_sc='TEST001',
            quantidade_solicitada=Decimal('1.00'),
            quantidade_recebida=Decimal('0.99')
        )
        
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra,
            quantidade_planejada=Decimal('1.00'),
            numero_sc='TEST001'
        )
        
        # Alocar 0.33 três vezes
        for i in range(3):
            AlocacaoRecebimento.objects.create(
                obra=obra,
                insumo=insumo,
                local_aplicacao=local_obra,
                recebimento=recebimento,
                item_mapa=item,
                quantidade_alocada=Decimal('0.33')
            )
        
        total_alocado = item.quantidade_alocada_local
        # Deve ser 0.99, não 1.00
        assert total_alocado == Decimal('0.99'), f"Esperado 0.99, obtido {total_alocado}"
    
    def test_arredondamento_financeiro(self, db):
        """Testa arredondamento financeiro (ROUND_HALF_UP)."""
        # 0.335 deve arredondar para 0.34 (não 0.33)
        valor = Decimal('0.335')
        arredondado = valor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        assert arredondado == Decimal('0.34'), f"Esperado 0.34, obtido {arredondado}"
        
        # 0.334 deve arredondar para 0.33
        valor2 = Decimal('0.334')
        arredondado2 = valor2.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        assert arredondado2 == Decimal('0.33'), f"Esperado 0.33, obtido {arredondado2}"


class TestDivisaoPorZero:
    """2. Divisão por Zero: O que acontece se quantidade for 0?"""
    
    def test_percentual_alocado_com_quantidade_zero(self, db, obra, insumo, local_obra):
        """Testa cálculo de percentual quando quantidade_planejada é 0."""
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra,
            quantidade_planejada=Decimal('0.00')
        )
        
        # Não deve quebrar, deve retornar 0.00
        percentual = item.percentual_alocado
        assert percentual == Decimal('0.00'), f"Esperado 0.00, obtido {percentual}"
    
    def test_percentual_alocado_com_solicitada_zero(self, db, obra, insumo, local_obra):
        """Testa cálculo de percentual quando quantidade_solicitada_sienge é 0."""
        recebimento = RecebimentoObra.objects.create(
            obra=obra,
            insumo=insumo,
            numero_sc='TEST002',
            quantidade_solicitada=Decimal('0.00'),
            quantidade_recebida=Decimal('0.00')
        )
        
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra,
            quantidade_planejada=Decimal('100.00'),
            numero_sc='TEST002'
        )
        
        # Deve usar quantidade_planejada como fallback
        percentual = item.percentual_alocado
        assert percentual == Decimal('0.00'), f"Esperado 0.00, obtido {percentual}"
    
    def test_quantidade_disponivel_com_recebido_zero(self, db, obra, insumo):
        """Testa quantidade_disponivel quando recebido é 0."""
        recebimento = RecebimentoObra.objects.create(
            obra=obra,
            insumo=insumo,
            numero_sc='TEST003',
            quantidade_solicitada=Decimal('100.00'),
            quantidade_recebida=Decimal('0.00')
        )
        
        disponivel = recebimento.quantidade_disponivel
        assert disponivel == Decimal('0.00'), f"Esperado 0.00, obtido {disponivel}"


class TestValoresNegativos:
    """3. Valores Negativos: O clean() do model impede isso?"""
    
    def test_quantidade_planejada_negativa_via_model(self, db, obra, insumo, local_obra):
        """Tenta criar ItemMapa com quantidade_planejada negativa."""
        # Django DecimalField com MinValueValidator deve bloquear
        with pytest.raises(ValidationError):
            item = ItemMapa(
                obra=obra,
                insumo=insumo,
                categoria='FUNDAÇÃO',
                local_aplicacao=local_obra,
                quantidade_planejada=Decimal('-10.00')
            )
            item.full_clean()
    
    def test_quantidade_alocada_negativa_via_model(self, db, obra, insumo, local_obra, recebimento_obra, item_mapa):
        """Tenta criar AlocacaoRecebimento com quantidade_alocada negativa."""
        with pytest.raises(ValidationError):
            alocacao = AlocacaoRecebimento(
                obra=obra,
                insumo=insumo,
                local_aplicacao=local_obra,
                recebimento=recebimento_obra,
                item_mapa=item_mapa,
                quantidade_alocada=Decimal('-5.00')
            )
            alocacao.full_clean()
    
    def test_quantidade_recebida_negativa_via_model(self, db, obra, insumo):
        """Tenta criar RecebimentoObra com quantidade_recebida negativa."""
        with pytest.raises(ValidationError):
            recebimento = RecebimentoObra(
                obra=obra,
                insumo=insumo,
                numero_sc='TEST004',
                quantidade_solicitada=Decimal('100.00'),
                quantidade_recebida=Decimal('-50.00')
            )
            recebimento.full_clean()
    
    def test_saldo_negativo_propriedade(self, db, obra, insumo, local_obra):
        """Testa se propriedades calculadas retornam valores negativos."""
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra,
            quantidade_planejada=Decimal('100.00')
        )
        
        # Criar alocação maior que planejado (deve ser permitido pelo sistema)
        recebimento = RecebimentoObra.objects.create(
            obra=obra,
            insumo=insumo,
            numero_sc='TEST005',
            quantidade_solicitada=Decimal('200.00'),
            quantidade_recebida=Decimal('200.00')
        )
        
        # Alocar mais do que planejado
        AlocacaoRecebimento.objects.create(
            obra=obra,
            insumo=insumo,
            local_aplicacao=local_obra,
            recebimento=recebimento,
            item_mapa=item,
            quantidade_alocada=Decimal('150.00')
        )
        
        # saldo_a_alocar_local deve retornar 0 (não negativo)
        saldo = item.saldo_a_alocar_local
        assert saldo >= Decimal('0.00'), f"Saldo não pode ser negativo, obtido {saldo}"


class TestConversaoUnidade:
    """4. Conversão de Unidade: Se houver lógica de conversão, teste precisão."""
    
    def test_precisao_multiplicacao_decimal(self, db):
        """Testa precisão em multiplicações (ex: Caixa para Unidade)."""
        # Exemplo: 1 caixa = 12 unidades
        caixas = Decimal('2.5')
        unidades_por_caixa = Decimal('12.00')
        total_unidades = caixas * unidades_por_caixa
        
        # Deve ser exatamente 30.00, não 29.999999 ou 30.000001
        assert total_unidades == Decimal('30.00'), f"Esperado 30.00, obtido {total_unidades}"
    
    def test_precisao_divisao_decimal(self, db):
        """Testa precisão em divisões."""
        # 100 unidades / 12 unidades por caixa = 8.33... caixas
        unidades = Decimal('100.00')
        unidades_por_caixa = Decimal('12.00')
        caixas = unidades / unidades_por_caixa
        
        # Deve ser aproximadamente 8.3333...
        assert caixas > Decimal('8.33'), f"Esperado > 8.33, obtido {caixas}"
        assert caixas < Decimal('8.34'), f"Esperado < 8.34, obtido {caixas}"
    
    def test_soma_multiplas_alocacoes_precisao(self, db, obra, insumo, local_obra, recebimento_obra, item_mapa):
        """Testa precisão na soma de múltiplas alocações."""
        # Criar 10 alocações de 0.1
        for i in range(10):
            AlocacaoRecebimento.objects.create(
                obra=obra,
                insumo=insumo,
                local_aplicacao=local_obra,
                recebimento=recebimento_obra,
                item_mapa=item_mapa,
                quantidade_alocada=Decimal('0.1')
            )
        
        total = item_mapa.quantidade_alocada_local
        # Deve ser exatamente 1.00, não 0.999999 ou 1.000001
        assert total == Decimal('1.00'), f"Esperado 1.00, obtido {total}"


class TestEdgeCasesMatematicos:
    """Casos extremos matemáticos."""
    
    def test_valores_muito_grandes(self, db, obra, insumo, local_obra):
        """Testa com valores muito grandes (limite do DecimalField)."""
        # max_digits=14, decimal_places=2 = máximo 999999999999.99
        valor_maximo = Decimal('999999999999.99')
        
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra,
            quantidade_planejada=valor_maximo
        )
        
        assert item.quantidade_planejada == valor_maximo
    
    def test_valores_muito_pequenos(self, db, obra, insumo, local_obra):
        """Testa com valores muito pequenos."""
        valor_minimo = Decimal('0.01')
        
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra,
            quantidade_planejada=valor_minimo
        )
        
        assert item.quantidade_planejada == valor_minimo
    
    def test_quantidade_zero_permitida(self, db, obra, insumo, local_obra):
        """Testa se quantidade zero é permitida (deve ser)."""
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra,
            quantidade_planejada=Decimal('0.00')
        )
        
        assert item.quantidade_planejada == Decimal('0.00')

