"""Testes leves para regras de casamento levantamento ↔ Sienge (sem pytest)."""
from django.test import SimpleTestCase

from suprimentos.recebimento_match import descricao_item_compativel


class DescricaoCompativelTests(SimpleTestCase):
    def test_igualdade_simples(self):
        self.assertTrue(descricao_item_compativel('Cimento CP II', 'cimento cp ii'))

    def test_substring_so_texto_longo(self):
        longa = 'TUBO PVC ESGOTO DN 100MM SERIE NORMAL'
        self.assertTrue(descricao_item_compativel(longa, longa + ' REFORCADO'))

    def test_ambiguo_curto_nao_casa_por_substring(self):
        self.assertFalse(descricao_item_compativel('KG', 'KG REF'))

    def test_sm_lev_nao_afeta_funcao(self):
        self.assertTrue(descricao_item_compativel('  A  B  ', 'a b'))

