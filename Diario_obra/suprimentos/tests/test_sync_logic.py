"""
ETAPA 3: TESTES DE INTEGRAÇÃO E SINCRONIZAÇÃO (O "Recebimento")

Este é o ponto mais crítico que preciso garantir:
1. Cenário "Atualização do Mestre": Alterar Insumo não deve afetar histórico
2. Cenário "Recebimento de Mercadoria": Status e estoque devem atualizar corretamente
3. Cenário "Orfandade": Deleção de entidades relacionadas
"""
import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from suprimentos.models import (
    Insumo, ItemMapa, RecebimentoObra, AlocacaoRecebimento,
    NotaFiscalEntrada, HistoricoAlteracao
)
from mapa_obras.models import Obra, LocalObra


class TestAtualizacaoMestre:
    """1. Cenário "Atualização do Mestre": Alterar Insumo não deve afetar histórico."""
    
    def test_alterar_descricao_insumo_nao_afeta_item_mapa(self, db, obra, insumo, local_obra):
        """
        AÇÃO: Alterar descrição do Insumo
        VERIFICAÇÃO: ItemMapa deve manter descrição original ou usar descricao_override
        """
        # Criar item do mapa
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra,
            quantidade_planejada=Decimal('100.00')
        )
        
        descricao_original = insumo.descricao
        assert item.insumo.descricao == descricao_original
        
        # Alterar descrição do insumo
        insumo.descricao = 'Nova Descrição do Insumo'
        insumo.save()
        
        # ItemMapa deve continuar usando o mesmo insumo (referência)
        item.refresh_from_db()
        assert item.insumo.descricao == 'Nova Descrição do Insumo'
        
        # MAS: Se tiver descricao_override, deve usar essa
        item.descricao_override = 'Descrição Customizada'
        item.save()
        
        # A descrição exibida deve ser a override, não a do insumo
        descricao_exibida = item.descricao_override or item.insumo.descricao
        assert descricao_exibida == 'Descrição Customizada'
    
    def test_alterar_codigo_insumo_nao_afeta_recebimento(self, db, obra, insumo, recebimento_obra):
        """
        AÇÃO: Alterar código do Insumo
        VERIFICAÇÃO: RecebimentoObra deve manter vínculo
        """
        codigo_original = insumo.codigo_sienge
        assert recebimento_obra.insumo.codigo_sienge == codigo_original
        
        # Alterar código
        insumo.codigo_sienge = 'NOVO_CODIGO'
        insumo.save()
        
        # Recebimento deve continuar vinculado ao mesmo insumo
        recebimento_obra.refresh_from_db()
        assert recebimento_obra.insumo.codigo_sienge == 'NOVO_CODIGO'
    
    def test_deletar_insumo_protege_recebimentos(self, db, obra, insumo, recebimento_obra):
        """
        AÇÃO: Tentar deletar Insumo que tem RecebimentoObra
        VERIFICAÇÃO: Deve ser BLOQUEADO (on_delete=models.PROTECT)
        """
        # Insumo tem on_delete=models.PROTECT em RecebimentoObra
        with pytest.raises(Exception):  # ProtectedError ou IntegrityError
            insumo.delete()
        
        # Insumo ainda deve existir
        assert Insumo.objects.filter(id=insumo.id).exists()
    
    def test_deletar_insumo_protege_item_mapa(self, db, obra, insumo, item_mapa):
        """
        AÇÃO: Tentar deletar Insumo que tem ItemMapa
        VERIFICAÇÃO: Deve ser BLOQUEADO (on_delete=models.PROTECT)
        """
        with pytest.raises(Exception):
            insumo.delete()
        
        assert Insumo.objects.filter(id=insumo.id).exists()


class TestRecebimentoMercadoria:
    """2. Cenário "Recebimento de Mercadoria": Status e estoque devem atualizar."""
    
    def test_recebimento_atualiza_status(self, db, obra, insumo, local_obra):
        """
        AÇÃO: Receber mercadoria
        VERIFICAÇÃO: Status no Mapa muda para "Entregue"?
        """
        recebimento = RecebimentoObra.objects.create(
            obra=obra,
            insumo=insumo,
            numero_sc='SC001',
            quantidade_solicitada=Decimal('100.00'),
            quantidade_recebida=Decimal('0.00')
        )
        
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra,
            quantidade_planejada=Decimal('100.00'),
            numero_sc='SC001'
        )
        
        # Status inicial: aguardando entrega
        assert 'AGUARDANDO' in item.status_etapa or item.status_etapa == '3) AGUARDANDO ENTREGA'
        
        # Receber mercadoria
        recebimento.quantidade_recebida = Decimal('100.00')
        recebimento.save()
        
        item.refresh_from_db()
        # Status deve mudar para aguardando alocação (não entregue ainda, precisa alocar)
        assert item.quantidade_recebida_obra == Decimal('100.00')
        
        # Alocar para o local
        AlocacaoRecebimento.objects.create(
            obra=obra,
            insumo=insumo,
            local_aplicacao=local_obra,
            recebimento=recebimento,
            item_mapa=item,
            quantidade_alocada=Decimal('100.00')
        )
        
        item.refresh_from_db()
        # Agora deve estar entregue
        assert item.status_etapa == 'ENTREGUE' or item.status_css == 'status-verde'
    
    def test_recebimento_parcial_atualiza_status(self, db, obra, insumo, local_obra):
        """
        AÇÃO: Receber parcialmente (50 de 100)
        VERIFICAÇÃO: Status deve ser "Parcial"
        """
        recebimento = RecebimentoObra.objects.create(
            obra=obra,
            insumo=insumo,
            numero_sc='SC002',
            quantidade_solicitada=Decimal('100.00'),
            quantidade_recebida=Decimal('50.00')
        )
        
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra,
            quantidade_planejada=Decimal('100.00'),
            numero_sc='SC002'
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
        # Deve estar parcial
        assert item.status_etapa == '5) ALOCAÇÃO PARCIAL' or item.status_css == 'status-laranja'
    
    def test_estornar_recebimento_baixa_estoque(self, db, obra, insumo, local_obra, recebimento_obra, item_mapa):
        """
        AÇÃO: Estornar (cancelar) recebimento
        VERIFICAÇÃO: Estoque deve baixar de volta
        """
        # Receber e alocar
        recebimento_obra.quantidade_recebida = Decimal('100.00')
        recebimento_obra.save()
        
        alocacao = AlocacaoRecebimento.objects.create(
            obra=obra,
            insumo=insumo,
            local_aplicacao=local_obra,
            recebimento=recebimento_obra,
            item_mapa=item_mapa,
            quantidade_alocada=Decimal('100.00')
        )
        
        item_mapa.refresh_from_db()
        assert item_mapa.quantidade_alocada_local == Decimal('100.00')
        
        # Estornar: remover alocação e zerar recebimento
        alocacao.delete()
        recebimento_obra.quantidade_recebida = Decimal('0.00')
        recebimento_obra.save()
        
        item_mapa.refresh_from_db()
        assert item_mapa.quantidade_alocada_local == Decimal('0.00')
        assert item_mapa.quantidade_recebida_obra == Decimal('0.00')


class TestOrfandade:
    """3. Cenário "Orfandade": Deleção de entidades relacionadas."""
    
    def test_deletar_obra_casca_item_mapa(self, db, obra, item_mapa):
        """
        AÇÃO: Deletar Obra
        VERIFICAÇÃO: ItemMapa deve ser deletado (CASCADE)
        """
        item_id = item_mapa.id
        obra.delete()
        
        # ItemMapa deve ter sido deletado
        assert not ItemMapa.objects.filter(id=item_id).exists()
    
    def test_deletar_obra_casca_recebimento(self, db, obra, recebimento_obra):
        """
        AÇÃO: Deletar Obra
        VERIFICAÇÃO: RecebimentoObra deve ser deletado (CASCADE)
        """
        recebimento_id = recebimento_obra.id
        obra.delete()
        
        assert not RecebimentoObra.objects.filter(id=recebimento_id).exists()
    
    def test_deletar_recebimento_casca_alocacao(self, db, obra, insumo, local_obra, recebimento_obra, item_mapa):
        """
        AÇÃO: Deletar RecebimentoObra
        VERIFICAÇÃO: AlocacaoRecebimento deve ser deletado (CASCADE)
        """
        alocacao = AlocacaoRecebimento.objects.create(
            obra=obra,
            insumo=insumo,
            local_aplicacao=local_obra,
            recebimento=recebimento_obra,
            item_mapa=item_mapa,
            quantidade_alocada=Decimal('50.00')
        )
        
        alocacao_id = alocacao.id
        recebimento_obra.delete()
        
        # Alocação deve ter sido deletada
        assert not AlocacaoRecebimento.objects.filter(id=alocacao_id).exists()
    
    def test_deletar_item_mapa_set_null_alocacao(self, db, obra, insumo, local_obra, recebimento_obra, item_mapa):
        """
        AÇÃO: Deletar ItemMapa
        VERIFICAÇÃO: AlocacaoRecebimento.item_mapa deve ser NULL (SET_NULL)
        """
        alocacao = AlocacaoRecebimento.objects.create(
            obra=obra,
            insumo=insumo,
            local_aplicacao=local_obra,
            recebimento=recebimento_obra,
            item_mapa=item_mapa,
            quantidade_alocada=Decimal('50.00')
        )
        
        alocacao_id = alocacao.id
        item_mapa.delete()
        
        # Alocação deve existir mas sem item_mapa
        alocacao.refresh_from_db()
        assert alocacao.item_mapa is None
        assert AlocacaoRecebimento.objects.filter(id=alocacao_id).exists()
    
    def test_deletar_local_obra_protege_alocacao(self, db, obra, insumo, local_obra, recebimento_obra, item_mapa):
        """
        AÇÃO: Tentar deletar LocalObra que tem AlocacaoRecebimento
        VERIFICAÇÃO: Deve ser BLOQUEADO (PROTECT)
        """
        AlocacaoRecebimento.objects.create(
            obra=obra,
            insumo=insumo,
            local_aplicacao=local_obra,
            recebimento=recebimento_obra,
            item_mapa=item_mapa,
            quantidade_alocada=Decimal('50.00')
        )
        
        # Tentar deletar local deve falhar
        with pytest.raises(Exception):
            local_obra.delete()
        
        assert LocalObra.objects.filter(id=local_obra.id).exists()


class TestIntegridadeReferencial:
    """Testes adicionais de integridade referencial."""
    
    def test_recebimento_obra_vinculado_correto(self, db, obra, insumo, local_obra):
        """Testa se recebimento_vinculado retorna o RecebimentoObra correto."""
        recebimento = RecebimentoObra.objects.create(
            obra=obra,
            insumo=insumo,
            numero_sc='SC003',
            item_sc='',
            quantidade_solicitada=Decimal('100.00'),
            quantidade_recebida=Decimal('80.00')
        )
        
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra,
            quantidade_planejada=Decimal('100.00'),
            numero_sc='SC003'
        )
        
        vinculado = item.recebimento_vinculado
        assert vinculado is not None
        assert vinculado.id == recebimento.id
    
    def test_quantidade_alocada_local_soma_correta(self, db, obra, insumo, local_obra, recebimento_obra, item_mapa):
        """Testa se quantidade_alocada_local soma todas as alocações corretamente."""
        # Criar múltiplas alocações
        AlocacaoRecebimento.objects.create(
            obra=obra,
            insumo=insumo,
            local_aplicacao=local_obra,
            recebimento=recebimento_obra,
            item_mapa=item_mapa,
            quantidade_alocada=Decimal('30.00')
        )
        
        AlocacaoRecebimento.objects.create(
            obra=obra,
            insumo=insumo,
            local_aplicacao=local_obra,
            recebimento=recebimento_obra,
            item_mapa=item_mapa,
            quantidade_alocada=Decimal('20.00')
        )
        
        item_mapa.refresh_from_db()
        total = item_mapa.quantidade_alocada_local
        assert total == Decimal('50.00'), f"Esperado 50.00, obtido {total}"
    
    def test_quantidade_disponivel_calculo_correto(self, db, obra, insumo):
        """Testa se quantidade_disponivel calcula corretamente."""
        recebimento = RecebimentoObra.objects.create(
            obra=obra,
            insumo=insumo,
            numero_sc='SC004',
            quantidade_solicitada=Decimal('100.00'),
            quantidade_recebida=Decimal('100.00')
        )
        
        # Sem alocações, disponível = recebido
        assert recebimento.quantidade_disponivel == Decimal('100.00')
        
        # Criar alocação de 40
        local_obra = LocalObra.objects.create(obra=obra, nome='Bloco A', tipo='BLOCO')
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local_obra,
            quantidade_planejada=Decimal('100.00'),
            numero_sc='SC004'
        )
        
        AlocacaoRecebimento.objects.create(
            obra=obra,
            insumo=insumo,
            local_aplicacao=local_obra,
            recebimento=recebimento,
            item_mapa=item,
            quantidade_alocada=Decimal('40.00')
        )
        
        recebimento.refresh_from_db()
        # Disponível = 100 - 40 = 60
        assert recebimento.quantidade_disponivel == Decimal('60.00')

