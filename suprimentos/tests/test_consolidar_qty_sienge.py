"""Testes para consolidação de qt. solicitada / entregue no import MAPA_CONTROLE (Sienge)."""
from decimal import Decimal

from django.test import SimpleTestCase

from suprimentos.utils_importacao import (
    consolidar_quantidade_entregue_sienge,
    consolidar_quantidades_sienge_linhas_csv,
    consolidar_quantidade_solicitada_sienge,
)


class ConsolidarQuantidadeSolicitadaSiengeTests(SimpleTestCase):
    def test_lista_vazia(self):
        self.assertEqual(consolidar_quantidade_solicitada_sienge([]), Decimal('0.00'))

    def test_uma_linha(self):
        self.assertEqual(
            consolidar_quantidade_solicitada_sienge([Decimal('8750')]),
            Decimal('8750'),
        )

    def test_sienge_repete_total_em_cada_linha(self):
        linhas = [Decimal('4000')] * 4
        self.assertEqual(consolidar_quantidade_solicitada_sienge(linhas), Decimal('4000'))

    def test_sc_parcelada_soma_parcelas(self):
        linhas = [Decimal('8750'), Decimal('10500'), Decimal('5978.80')]
        esperado = Decimal('25228.80')
        self.assertEqual(consolidar_quantidade_solicitada_sienge(linhas), esperado)

    def test_entrega_alias_mesma_logica(self):
        linhas = [Decimal('100'), Decimal('50')]
        self.assertEqual(
            consolidar_quantidade_entregue_sienge(linhas),
            Decimal('150'),
        )
        self.assertEqual(
            consolidar_quantidades_sienge_linhas_csv([Decimal('9')] * 3),
            Decimal('9'),
        )
