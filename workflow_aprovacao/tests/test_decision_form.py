from django.contrib.auth import get_user_model
from django.test import SimpleTestCase

from workflow_aprovacao.forms import DecisionForm

User = get_user_model()
_VALID_SIG = 'data:image/png;base64,' + ('A' * 600)


class DecisionFormSignatureTests(SimpleTestCase):
    def test_exige_assinatura_manual(self):
        user = User(username='u1')
        form = DecisionForm(
            {
                'signer_name': 'u1',
                'confirm_read': True,
                'signature_data': '',
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn('signature_data', form.errors)

    def test_aceita_assinatura_png(self):
        user = User(username='u1')
        form = DecisionForm(
            {
                'signer_name': 'u1',
                'confirm_read': True,
                'signature_data': _VALID_SIG,
            }
        )
        self.assertTrue(form.is_valid())
        form.validate_for_action(action='approve', user=user, process_id=10)
        self.assertFalse(form.errors.get('signer_name'))
