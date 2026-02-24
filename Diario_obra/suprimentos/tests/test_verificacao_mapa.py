"""
Testes da verificação do Mapa de Suprimentos.

Garante que run_verificacao() cobre todos os casos e que dados consistentes
passam e dados inconsistentes são detectados.

Rodar com: python manage.py test suprimentos.tests.test_verificacao_mapa -v 2
"""
from decimal import Decimal
from io import StringIO
from django.test import TestCase
from django.core.management import call_command

from mapa_obras.models import Obra, LocalObra
from suprimentos.models import Insumo, ItemMapa, RecebimentoObra, AlocacaoRecebimento
from suprimentos.management.commands.verificar_mapa_suprimentos import run_verificacao


class TestVerificacaoMapaSuprimentos(TestCase):
    """Testes da verificação de consistência do mapa."""

    def test_verificacao_banco_vazio(self):
        """Banco vazio deve passar (nenhum erro de consistência)."""
        erros, avisos = run_verificacao(verbose=False)
        self.assertEqual(len(erros), 0, f'Esperado 0 erros, obtido: {erros}')

    def test_verificacao_dados_consistentes(self):
        """Dados consistentes: 1 RecebimentoObra + 1 ItemMapa vinculado; verificação deve passar."""
        obra = Obra.objects.create(
            codigo_sienge='OBR-TEST-1',
            nome='Obra Teste',
            ativa=True,
        )
        local = LocalObra.objects.create(obra=obra, nome='Bloco A', tipo='BLOCO')
        insumo = Insumo.objects.create(
            codigo_sienge='INS-TEST-1',
            descricao='Insumo Teste',
            unidade='KG',
            ativo=True,
            eh_macroelemento=True,
        )
        RecebimentoObra.objects.create(
            obra=obra,
            insumo=insumo,
            numero_sc='SC-2026-001',
            item_sc='',
            quantidade_solicitada=Decimal('1000.00'),
            quantidade_recebida=Decimal('600.00'),
            saldo_a_entregar=Decimal('400.00'),
        )
        ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local,
            quantidade_planejada=Decimal('1000.00'),
            numero_sc='SC-2026-001',
            item_sc='',
        )
        erros, avisos = run_verificacao(verbose=False)
        self.assertEqual(len(erros), 0, f'Dados consistentes devem passar. Erros: {erros}')

    def test_verificacao_detecta_recebido_mais_saldo_maior_que_solicitado(self):
        """Se recebido + saldo > solicitado, deve gerar erro."""
        obra = Obra.objects.create(codigo_sienge='OBR-T2', nome='Obra 2', ativa=True)
        insumo = Insumo.objects.create(
            codigo_sienge='INS-T2', descricao='Insumo 2', unidade='KG', ativo=True, eh_macroelemento=True
        )
        RecebimentoObra.objects.create(
            obra=obra,
            insumo=insumo,
            numero_sc='SC-2026-002',
            item_sc='',
            quantidade_solicitada=Decimal('100.00'),
            quantidade_recebida=Decimal('60.00'),
            saldo_a_entregar=Decimal('50.00'),  # 60+50=110 > 100
        )
        erros, avisos = run_verificacao(verbose=False)
        self.assertTrue(any('recebido+saldo' in e for e in erros), f'Esperado erro de coerência. Erros: {erros}')

    def test_verificacao_item_com_sc_sem_recebimento_vinculado(self):
        """ItemMapa com numero_sc sem RecebimentoObra correspondente deve gerar erro."""
        obra = Obra.objects.create(codigo_sienge='OBR-T3', nome='Obra 3', ativa=True)
        local = LocalObra.objects.create(obra=obra, nome='Bloco A', tipo='BLOCO')
        insumo = Insumo.objects.create(
            codigo_sienge='INS-T3', descricao='Insumo 3', unidade='KG', ativo=True, eh_macroelemento=True
        )
        ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local,
            quantidade_planejada=Decimal('100.00'),
            numero_sc='SC-FANTASMA',
            item_sc='',
        )
        erros, avisos = run_verificacao(verbose=False)
        self.assertTrue(
            any('sem RecebimentoObra vinculado' in e for e in erros),
            f'Esperado erro de vínculo. Erros: {erros}'
        )

    def test_verificacao_alocacao_nao_ultrapassa_recebido(self):
        """Alocação total não pode ultrapassar quantidade_recebida. (Modelo impede criar inválido; forçamos com update.)"""
        obra = Obra.objects.create(codigo_sienge='OBR-T4', nome='Obra 4', ativa=True)
        local = LocalObra.objects.create(obra=obra, nome='Bloco A', tipo='BLOCO')
        insumo = Insumo.objects.create(
            codigo_sienge='INS-T4', descricao='Insumo 4', unidade='KG', ativo=True, eh_macroelemento=True
        )
        rec = RecebimentoObra.objects.create(
            obra=obra,
            insumo=insumo,
            numero_sc='SC-2026-004',
            item_sc='',
            quantidade_solicitada=Decimal('1000.00'),
            quantidade_recebida=Decimal('500.00'),
            saldo_a_entregar=Decimal('500.00'),
        )
        item = ItemMapa.objects.create(
            obra=obra,
            insumo=insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=local,
            quantidade_planejada=Decimal('1000.00'),
            numero_sc='SC-2026-004',
            item_sc='',
        )
        aloc = AlocacaoRecebimento.objects.create(
            obra=obra,
            insumo=insumo,
            local_aplicacao=local,
            recebimento=rec,
            item_mapa=item,
            quantidade_alocada=Decimal('300.00'),  # válido
        )
        # Forçar estado inconsistente (o modelo não deixa criar 600 direto)
        AlocacaoRecebimento.objects.filter(pk=aloc.pk).update(quantidade_alocada=Decimal('600.00'))
        erros, avisos = run_verificacao(verbose=False)
        self.assertTrue(any('soma alocações' in e for e in erros), f'Esperado erro de alocação. Erros: {erros}')

    def test_comando_verificar_mapa_suprimentos_roda(self):
        """O comando manage.py verificar_mapa_suprimentos executa sem exceção."""
        out = StringIO()
        call_command('verificar_mapa_suprimentos', stdout=out)
        saida = out.getvalue()
        self.assertTrue('VERIFICAÇÃO' in saida or 'Contagens' in saida, f'Saída: {saida[:200]}')
