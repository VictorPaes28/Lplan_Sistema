from django.test import SimpleTestCase

from gestao_aprovacao.signature_utils import validate_signature_data

_VALID = 'data:image/png;base64,' + ('x' * 600)


class ApprovalSignatureValidationTests(SimpleTestCase):
    def test_rejeita_vazio(self):
        with self.assertRaises(ValueError):
            validate_signature_data('')

    def test_rejeita_prefixo_invalido(self):
        with self.assertRaises(ValueError):
            validate_signature_data('not-an-image')

    def test_aceita_png_base64(self):
        self.assertEqual(validate_signature_data(_VALID), _VALID)
