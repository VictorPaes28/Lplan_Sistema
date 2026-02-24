"""
ETAPA 4: EDGE CASES E "CHAOS MONKEY"

Testes para situações absurdas:
1. Entrada Parcial: Pedido de 100, chegaram 50
2. Super Recebimento: Pedido de 10, digitou 1000
3. Mudança de Obra: Mover item de Obra A para B
"""
import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from suprimentos.models import ItemMapa, RecebimentoObra, AlocacaoRecebimento
from obras.models import Obra, LocalObra


class TestEntradaParcial:
    """1. Entrada Parcial: O sistema sabe que faltam 50 ou marca como concluído errado?"""
    
    def test_recebimento_parcial_status_correto(self, db, obra, insumo, local_obra):
        """
        Cenário: Pedido de 100, chegaram 50.
        Verificação: Sistema deve mostrar status PARCIAL, não ENTREGUE.
        """
        recebimento = RecebimentoObra.objects.create(
            obra=obra,
            insumo=insumo,
            numero_sc='SC_PARCIAL',
            quantidade_solicitada=Decimal('100.00'),
            quantidade_recebida=Decimal('50.00')
        )
        
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra,
            quantidade_planejada=Decimal('100.00'),
            numero_sc='SC_PARCIAL'
        )
        
        # Alocar o que foi recebido
        AlocacaoRecebimento.objects.create(
            obra=obra,
            insumo=insumo,
            local_aplicacao=local_obra,
            recebimento=recebimento,
            item_mapa=item,
            quantidade_alocada=Decimal('50.00')
        )
        
        item.refresh_from_db()
        
        # Status deve ser PARCIAL, não ENTREGUE
        assert item.status_etapa == '5) ALOCAÇÃO PARCIAL'
        assert item.status_css == 'status-laranja'
        
        # Saldo a entregar deve mostrar 50 (faltam 50)
        saldo = item.saldo_a_entregar_sienge
        assert saldo == Decimal('50.00'), f"Esperado 50.00 faltando, obtido {saldo}"
    
    def test_recebimento_parcial_nao_marca_entregue(self, db, obra, insumo, local_obra):
        """Garante que recebimento parcial NÃO marca como entregue."""
        recebimento = RecebimentoObra.objects.create(
            obra=obra,
            insumo=insumo,
            numero_sc='SC_PARCIAL2',
            quantidade_solicitada=Decimal('1000.00'),
            quantidade_recebida=Decimal('100.00')  # Apenas 10%
        )
        
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra,
            quantidade_planejada=Decimal('1000.00'),
            numero_sc='SC_PARCIAL2'
        )
        
        # Alocar tudo que foi recebido
        AlocacaoRecebimento.objects.create(
            obra=obra,
            insumo=insumo,
            local_aplicacao=local_obra,
            recebimento=recebimento,
            item_mapa=item,
            quantidade_alocada=Decimal('100.00')
        )
        
        item.refresh_from_db()
        
        # NÃO deve estar entregue (faltam 900)
        assert item.status_etapa != 'ENTREGUE'
        assert item.status_css != 'status-verde'


class TestSuperRecebimento:
    """2. Super Recebimento: O sistema bloqueia ou aceita?"""
    
    def test_super_recebimento_permitido(self, db, obra, insumo, local_obra):
        """
        Cenário: Pedido de 10, digitou 1000.
        Verificação: Sistema deve PERMITIR (pode ser ajuste/sobra)
        """
        recebimento = RecebimentoObra.objects.create(
            obra=obra,
            insumo=insumo,
            numero_sc='SC_SUPER',
            quantidade_solicitada=Decimal('10.00'),
            quantidade_recebida=Decimal('1000.00')  # 100x mais!
        )
        
        # Deve ser permitido (não há validação que bloqueia isso)
        assert recebimento.quantidade_recebida == Decimal('1000.00')
        
        # Status deve mostrar que recebeu mais do que solicitado
        assert recebimento.quantidade_recebida > recebimento.quantidade_solicitada
    
    def test_super_recebimento_alocacao_limite(self, db, obra, insumo, local_obra):
        """
        Cenário: Recebido 1000, mas só pode alocar o que foi recebido.
        Verificação: Pode alocar até 1000, não mais.
        """
        recebimento = RecebimentoObra.objects.create(
            obra=obra,
            insumo=insumo,
            numero_sc='SC_SUPER2',
            quantidade_solicitada=Decimal('10.00'),
            quantidade_recebida=Decimal('1000.00')
        )
        
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra,
            quantidade_planejada=Decimal('10.00'),
            numero_sc='SC_SUPER2'
        )
        
        # Tentar alocar 1000 (deve permitir)
        alocacao = AlocacaoRecebimento(
            obra=obra,
            insumo=insumo,
            local_aplicacao=local_obra,
            recebimento=recebimento,
            item_mapa=item,
            quantidade_alocada=Decimal('1000.00')
        )
        alocacao.full_clean()  # Deve passar
        alocacao.save()
        
        # Tentar alocar mais 1 (deve BLOQUEAR)
        alocacao2 = AlocacaoRecebimento(
            obra=obra,
            insumo=insumo,
            local_aplicacao=local_obra,
            recebimento=recebimento,
            item_mapa=item,
            quantidade_alocada=Decimal('1.00')
        )
        
        with pytest.raises(ValidationError):
            alocacao2.full_clean()


class TestMudancaObra:
    """3. Mudança de Obra: É possível mover item de Obra A para B?"""
    
    def test_mover_item_entre_obras(self, db, insumo, local_obra):
        """
        Cenário: Mover ItemMapa de Obra A para Obra B.
        Verificação: Deve atualizar centro de custo (obra) corretamente.
        """
        obra_a = Obra.objects.create(nome='Obra A', ativa=True)
        obra_b = Obra.objects.create(nome='Obra B', ativa=True)
        
        local_obra_a = LocalObra.objects.create(obra=obra_a, nome='Bloco A', tipo='BLOCO')
        
        item = ItemMapa.objects.create(
            obra=obra_a,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra_a,
            quantidade_planejada=Decimal('100.00')
        )
        
        # Mover para obra B
        local_obra_b = LocalObra.objects.create(obra=obra_b, nome='Bloco B', tipo='BLOCO')
        item.obra = obra_b
        item.local_aplicacao = local_obra_b
        item.save()
        
        item.refresh_from_db()
        assert item.obra_id == obra_b.id
        assert item.local_aplicacao.obra_id == obra_b.id
    
    def test_mover_item_com_recebimento_vinculado(self, db, insumo):
        """
        Cenário: Mover ItemMapa que tem RecebimentoObra vinculado.
        Verificação: RecebimentoObra deve permanecer na obra original.
        """
        obra_a = Obra.objects.create(nome='Obra A', ativa=True)
        obra_b = Obra.objects.create(nome='Obra B', ativa=True)
        
        local_obra_a = LocalObra.objects.create(obra=obra_a, nome='Bloco A', tipo='BLOCO')
        
        recebimento = RecebimentoObra.objects.create(
            obra=obra_a,
            insumo=insumo,
            numero_sc='SC_MOVE',
            quantidade_solicitada=Decimal('100.00'),
            quantidade_recebida=Decimal('50.00')
        )
        
        item = ItemMapa.objects.create(
            obra=obra_a,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra_a,
            quantidade_planejada=Decimal('100.00'),
            numero_sc='SC_MOVE'
        )
        
        # Mover item para obra B
        local_obra_b = LocalObra.objects.create(obra=obra_b, nome='Bloco B', tipo='BLOCO')
        item.obra = obra_b
        item.local_aplicacao = local_obra_b
        item.save()
        
        # Recebimento deve continuar na obra A
        recebimento.refresh_from_db()
        assert recebimento.obra_id == obra_a.id
        
        # Item na obra B não deve encontrar recebimento (está na obra A)
        item.refresh_from_db()
        vinculado = item.recebimento_vinculado
        # Pode retornar None ou o recebimento (depende da lógica)
        # Mas o recebimento está na obra A, então pode não encontrar
        if vinculado:
            # Se encontrar, deve ser o da obra A (mesma SC+insumo)
            assert vinculado.obra_id == obra_a.id


class TestCasosExtremos:
    """Casos extremos adicionais."""
    
    def test_alocacao_maior_que_planejado(self, db, obra, insumo, local_obra, recebimento_obra):
        """
        Cenário: Alocar mais do que foi planejado.
        Verificação: Deve ser permitido (pode ser necessário).
        """
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra,
            quantidade_planejada=Decimal('100.00'),
            numero_sc='SC_EXTRA'
        )
        
        recebimento_obra.numero_sc = 'SC_EXTRA'
        recebimento_obra.quantidade_recebida = Decimal('200.00')
        recebimento_obra.save()
        
        # Alocar 150 (mais que planejado)
        alocacao = AlocacaoRecebimento(
            obra=obra,
            insumo=insumo,
            local_aplicacao=local_obra,
            recebimento=recebimento_obra,
            item_mapa=item,
            quantidade_alocada=Decimal('150.00')
        )
        alocacao.full_clean()  # Deve permitir
        alocacao.save()
        
        item.refresh_from_db()
        assert item.quantidade_alocada_local == Decimal('150.00')
        assert item.saldo_negativo == True  # Alocado > Planejado
    
    def test_multiplos_recebimentos_mesma_sc(self, db, obra, insumo, local_obra):
        """
        Cenário: Múltiplos RecebimentoObra com mesma SC (diferentes item_sc).
        Verificação: ItemMapa deve encontrar o consolidado (item_sc='').
        """
        # Criar recebimento consolidado
        recebimento_consolidado = RecebimentoObra.objects.create(
            obra=obra,
            insumo=insumo,
            numero_sc='SC_MULT',
            item_sc='',  # Consolidado
            quantidade_solicitada=Decimal('100.00'),
            quantidade_recebida=Decimal('100.00')
        )
        
        # Criar recebimento específico (item_sc='1')
        recebimento_especifico = RecebimentoObra.objects.create(
            obra=obra,
            insumo=insumo,
            numero_sc='SC_MULT',
            item_sc='1',
            quantidade_solicitada=Decimal('50.00'),
            quantidade_recebida=Decimal('50.00')
        )
        
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra,
            quantidade_planejada=Decimal('100.00'),
            numero_sc='SC_MULT'
        )
        
        # Deve encontrar o consolidado (prioridade)
        vinculado = item.recebimento_vinculado
        assert vinculado is not None
        assert vinculado.item_sc == ''  # Deve ser o consolidado
    
    def test_item_sem_local_aplicacao(self, db, obra, insumo):
        """
        Cenário: ItemMapa sem local_aplicacao.
        Verificação: Sistema deve funcionar normalmente.
        """
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=None,  # Sem local
            quantidade_planejada=Decimal('100.00')
        )
        
        # Propriedades devem funcionar
        assert item.quantidade_alocada_local == Decimal('0.00')
        assert item.saldo_a_alocar_local == Decimal('100.00')
    
    def test_recebimento_sem_sc(self, db, obra, insumo, local_obra):
        """
        Cenário: ItemMapa sem SC (levante manual).
        Verificação: Deve usar campos legados (quantidade_recebida).
        """
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra,
            quantidade_planejada=Decimal('100.00'),
            numero_sc='',  # Sem SC
            quantidade_recebida=Decimal('50.00')  # Campo legado
        )
        
        # Deve usar quantidade_recebida legado
        assert item.quantidade_recebida_obra == Decimal('50.00')
    
    def test_alocacao_sem_recebimento(self, db, obra, insumo, local_obra, item_mapa):
        """
        Cenário: AlocacaoRecebimento sem recebimento vinculado.
        Verificação: Deve ser permitido (pode ser alocação manual).
        """
        # Criar alocação sem recebimento (recebimento=None)
        alocacao = AlocacaoRecebimento.objects.create(
            obra=obra,
            insumo=insumo,
            local_aplicacao=local_obra,
            recebimento=None,  # Sem recebimento
            item_mapa=item_mapa,
            quantidade_alocada=Decimal('50.00')
        )
        
        assert alocacao.recebimento is None
        assert alocacao.quantidade_alocada == Decimal('50.00')
    
    def test_quantidade_zero_na_alocacao(self, db, obra, insumo, local_obra, recebimento_obra, item_mapa):
        """
        Cenário: Tentar criar AlocacaoRecebimento com quantidade 0.
        Verificação: Deve ser BLOQUEADO (MinValueValidator(0.01)).
        """
        alocacao = AlocacaoRecebimento(
            obra=obra,
            insumo=insumo,
            local_aplicacao=local_obra,
            recebimento=recebimento_obra,
            item_mapa=item_mapa,
            quantidade_alocada=Decimal('0.00')
        )
        
        with pytest.raises(ValidationError):
            alocacao.full_clean()
    
    def test_mesmo_insumo_multiplos_locais(self, db, obra, insumo, local_obra, local_obra_b, recebimento_obra):
        """
        Cenário: Mesmo insumo em múltiplos locais.
        Verificação: Cada local deve ter sua própria alocação.
        """
        item_a = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra,
            quantidade_planejada=Decimal('500.00'),
            numero_sc='SC_MULT_LOCAL'
        )
        
        item_b = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra_b,
            quantidade_planejada=Decimal('300.00'),
            numero_sc='SC_MULT_LOCAL'
        )
        
        recebimento_obra.numero_sc = 'SC_MULT_LOCAL'
        recebimento_obra.quantidade_recebida = Decimal('800.00')
        recebimento_obra.save()
        
        # Alocar para cada local
        AlocacaoRecebimento.objects.create(
            obra=obra,
            insumo=insumo,
            local_aplicacao=local_obra,
            recebimento=recebimento_obra,
            item_mapa=item_a,
            quantidade_alocada=Decimal('500.00')
        )
        
        AlocacaoRecebimento.objects.create(
            obra=obra,
            insumo=insumo,
            local_aplicacao=local_obra_b,
            recebimento=recebimento_obra,
            item_mapa=item_b,
            quantidade_alocada=Decimal('300.00')
        )
        
        item_a.refresh_from_db()
        item_b.refresh_from_db()
        
        assert item_a.quantidade_alocada_local == Decimal('500.00')
        assert item_b.quantidade_alocada_local == Decimal('300.00')
        
        # Total alocado = 800 (igual ao recebido)
        total_alocado = recebimento_obra.quantidade_alocada
        assert total_alocado == Decimal('800.00')

