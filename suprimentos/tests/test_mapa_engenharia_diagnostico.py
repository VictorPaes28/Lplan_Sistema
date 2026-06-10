"""Diagnóstico de vínculo Sienge no mapa de engenharia."""
from decimal import Decimal

from django.test import TestCase

from mapa_obras.models import Obra
from suprimentos.models import Insumo, ItemMapa, RecebimentoObra
from suprimentos.services.mapa_engenharia_diagnostico import (
    alertas_codigo_descricao_duplicada,
    diagnostico_vinculo_sienge_item,
)


class TestMapaEngenhariaDiagnostico(TestCase):
    def setUp(self):
        self.obra = Obra.objects.create(codigo_sienge='OBR-DIAG', nome='Obra Diag', ativa=True)
        self.insumo = Insumo.objects.create(codigo_sienge='1001', descricao='Produto A', unidade='KG')
    def test_sem_sc_nivel_info(self):
        item = ItemMapa.objects.create(obra=self.obra, insumo=self.insumo, quantidade_planejada=Decimal('1'))
        d = diagnostico_vinculo_sienge_item(item)
        self.assertEqual(d['nivel'], 'info')
        self.assertIn('Sem SC', d['mensagem'])

    def test_sc_sem_codigo_sienge_aviso(self):
        lev = Insumo.objects.create(codigo_sienge='SM-LEV-XX', descricao='Aço', unidade='KG')
        item = ItemMapa.objects.create(
            obra=self.obra, insumo=lev, numero_sc='77', quantidade_planejada=Decimal('1')
        )
        d = diagnostico_vinculo_sienge_item(item)
        self.assertEqual(d['nivel'], 'aviso')
        self.assertIn('código', d['mensagem'].lower())

    def test_sc_codigo_sem_recebimento_aviso(self):
        item = ItemMapa.objects.create(
            obra=self.obra, insumo=self.insumo, numero_sc='77', quantidade_planejada=Decimal('1')
        )
        d = diagnostico_vinculo_sienge_item(item)
        self.assertEqual(d['nivel'], 'aviso')
        self.assertIn('nenhum recebimento', d['mensagem'].lower())

    def test_vinculo_ok_com_recebimento(self):
        RecebimentoObra.objects.create(
            obra=self.obra,
            insumo=self.insumo,
            numero_sc='77',
            item_sc='',
            quantidade_solicitada=Decimal('50'),
            quantidade_recebida=Decimal('0'),
        )
        item = ItemMapa.objects.create(
            obra=self.obra, insumo=self.insumo, numero_sc='77', quantidade_planejada=Decimal('1')
        )
        d = diagnostico_vinculo_sienge_item(item)
        self.assertEqual(d['nivel'], 'ok')

    def test_alerta_codigo_descricoes_diferentes(self):
        i1 = ItemMapa.objects.create(
            obra=self.obra,
            insumo=self.insumo,
            descricao_override='Aço 6.3 mm',
            quantidade_planejada=Decimal('1'),
        )
        i2 = ItemMapa.objects.create(
            obra=self.obra,
            insumo=self.insumo,
            descricao_override='FERRO 5.0 mm',
            quantidade_planejada=Decimal('2'),
        )
        alertas = alertas_codigo_descricao_duplicada([i1, i2])
        self.assertEqual(len(alertas), 1)
        self.assertIn('1001', alertas[0])
