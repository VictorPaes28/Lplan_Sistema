"""
Reprodução controlada dos cenários órfãos parcelados (popover).
Rodar: python manage.py test suprimentos.tests.test_popover_parcel_orphan_repro -v 2

Remove dados de teste no tearDown quando possível.
"""
import os
import tempfile
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from mapa_obras.models import Obra, LocalObra
from suprimentos.models import ImportacaoSienge, Insumo, ItemMapa, RecebimentoObra
from suprimentos.views_engenharia import _attach_recebimentos_obra_cache


def _csv(lines):
    """linhas já com ; — sem header duplicado."""
    return '\n'.join(lines) + '\n'


class PopoverParcelOrphanReproTestCase(TestCase):
    COD_OBRA = '99998'
    COD_INSUMO = '77701'
    NUM_SC = '558877'

    def setUp(self):
        self.obra = Obra.objects.create(
            codigo_sienge=self.COD_OBRA,
            nome='Obra teste popover parcel',
            ativa=True,
        )
        self.local = LocalObra.objects.create(
            obra=self.obra,
            nome='Local teste',
            tipo='BLOCO',
        )
        self.insumo = Insumo.objects.create(
            codigo_sienge=self.COD_INSUMO,
            descricao='Insumo teste parcel',
            unidade='UND',
            ativo=True,
            eh_macroelemento=True,
        )
        self.item_mapa = ItemMapa.objects.create(
            obra=self.obra,
            insumo=self.insumo,
            categoria='FUNDAÇÃO',
            local_aplicacao=self.local,
            quantidade_planejada=Decimal('30.00'),
            numero_sc=self.NUM_SC,
        )

    def tearDown(self):
        RecebimentoObra.objects.filter(obra=self.obra).delete()
        ImportacaoSienge.objects.filter(obra=self.obra).delete()
        self.item_mapa.delete()
        self.insumo.delete()
        self.local.delete()
        self.obra.delete()

    def _hdr(self):
        return (
            'CÓD. OBRA;Nº DA SC;CÓD. INSUMO;DESCRIÇÃO DO INSUMO;ITEM;'
            'QT. SOLICITADA;QUANT. ENTREGUE;Nº DO PC'
        )

    def _row(self, item_sc, qsol, qent):
        return (
            f'{self.COD_OBRA};{self.NUM_SC};{self.COD_INSUMO};Insumo teste parcel;'
            f'{item_sc};{qsol};{qent};PC-TEST-1'
        )

    def _import_file(self, content, sha_suffix, imp=None):
        path = tempfile.mktemp(suffix='.csv')
        try:
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(content)
            kwargs = {'file': path, 'obra_codigo': self.COD_OBRA, 'verbosity': 0, 'stdout': StringIO()}
            if imp:
                kwargs['importacao_id'] = imp.pk
            call_command('importar_mapa_controle', **kwargs)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def _parcel_item_scs(self):
        return sorted(
            RecebimentoObra.objects.filter(
                obra=self.obra,
                numero_sc=self.NUM_SC,
                insumo=self.insumo,
            )
            .exclude(item_sc='')
            .values_list('item_sc', flat=True)
        )

    def _consolidado(self):
        return RecebimentoObra.objects.filter(
            obra=self.obra,
            numero_sc=self.NUM_SC,
            insumo=self.insumo,
            item_sc='',
        ).first()

    def _popover_etapas_len(self):
        items = list(ItemMapa.objects.filter(pk=self.item_mapa.pk).select_related('insumo'))
        _attach_recebimentos_obra_cache(items, self.obra.pk)
        it = items[0]
        return it.total_etapas_entrega, it.has_entrega_parcelada, list(it.etapas_entrega)

    def test_a_then_b_orphan_shows_three_steps_in_popover(self):
        imp_a = ImportacaoSienge.objects.create(
            obra=self.obra,
            nome_arquivo='A.csv',
            sha256_arquivo='hash_a_unique_parcel',
        )
        csv_a = _csv(
            [
                self._hdr(),
                self._row(1, 10, 2),
                self._row(2, 15, 3),
                self._row(3, 5, 4),
            ]
        )
        self._import_file(csv_a, 'a', imp_a)

        self.assertEqual(self._parcel_item_scs(), ['1', '2', '3'])
        n, has_p, _ = self._popover_etapas_len()
        self.assertTrue(has_p)
        self.assertEqual(n, 3)

        cons = self._consolidado()
        self.assertIsNotNone(cons)
        # Valores de solicitado diferentes por linha → consolidado soma 10+15+5
        self.assertEqual(cons.quantidade_solicitada, Decimal('30'))
        # Entregues diferentes → soma 2+3+4
        self.assertEqual(cons.quantidade_recebida, Decimal('9'))

        imp_b = ImportacaoSienge.objects.create(
            obra=self.obra,
            nome_arquivo='B.csv',
            sha256_arquivo='hash_b_unique_parcel',
        )
        csv_b = _csv(
            [
                self._hdr(),
                self._row(1, 10, 5),
                self._row(2, 10, 6),
            ]
        )
        self._import_file(csv_b, 'b', imp_b)

        # Órfão: item 3 permanece no banco
        self.assertEqual(self._parcel_item_scs(), ['1', '2', '3'])
        n_after, has_p_after, etapas = self._popover_etapas_len()
        self.assertTrue(has_p_after)
        self.assertEqual(n_after, 3)
        # Etapa 3 ainda com quantidades antigas (não atualizadas pelo B)
        sc_3 = next(e for e in etapas if e['item_sc'] == '3')
        self.assertEqual(sc_3['quantidade_entregue'], Decimal('4'))

        cons2 = self._consolidado()
        self.assertEqual(cons2.quantidade_solicitada, Decimal('10'))
        self.assertEqual(cons2.quantidade_recebida, Decimal('11'))

    def test_reimport_same_content_no_extra_rows(self):
        imp = ImportacaoSienge.objects.create(
            obra=self.obra,
            nome_arquivo='A2.csv',
            sha256_arquivo='hash_same_parcel',
        )
        csv_a = _csv(
            [
                self._hdr(),
                self._row(1, 10, 1),
                self._row(2, 10, 2),
            ]
        )
        self._import_file(csv_a, '1', imp)
        c1 = RecebimentoObra.objects.filter(obra=self.obra, insumo=self.insumo).count()
        self._import_file(csv_a, '2', imp)
        c2 = RecebimentoObra.objects.filter(obra=self.obra, insumo=self.insumo).count()
        self.assertEqual(c1, c2)

    def test_desfazer_remove_only_importacao_linked_rows(self):
        imp_a = ImportacaoSienge.objects.create(
            obra=self.obra,
            nome_arquivo='A3.csv',
            sha256_arquivo='hash_undo_a',
        )
        csv_a = _csv(
            [
                self._hdr(),
                self._row(1, 10, 1),
                self._row(2, 10, 2),
                self._row(3, 10, 3),
            ]
        )
        self._import_file(csv_a, 'a', imp_a)

        imp_b = ImportacaoSienge.objects.create(
            obra=self.obra,
            nome_arquivo='B3.csv',
            sha256_arquivo='hash_undo_b',
        )
        csv_b = _csv(
            [
                self._hdr(),
                self._row(1, 10, 4),
                self._row(2, 10, 5),
            ]
        )
        self._import_file(csv_b, 'b', imp_b)

        # Após B, parcelas 1 e 2 apontam para imp_b; 3 permanece imp_a
        r3 = RecebimentoObra.objects.get(
            obra=self.obra, insumo=self.insumo, item_sc='3'
        )
        self.assertEqual(r3.importacao_id, imp_a.pk)
        r1 = RecebimentoObra.objects.get(
            obra=self.obra, insumo=self.insumo, item_sc='1'
        )
        self.assertEqual(r1.importacao_id, imp_b.pk)

        RecebimentoObra.objects.filter(importacao=imp_b).delete()
        imp_b.delete()

        rem = self._parcel_item_scs()
        self.assertEqual(rem, ['3'])
        n, _, _ = self._popover_etapas_len()
        self.assertEqual(n, 0)
