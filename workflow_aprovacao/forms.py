from django import forms
from django.core.exceptions import ValidationError

from core.models import Project
from workflow_aprovacao.models import ProcessCategory


class CommentForm(forms.Form):
    comment = forms.CharField(
        label='Comentário',
        required=False,
        widget=forms.Textarea(
            attrs={'rows': 3, 'class': 'wf-textarea', 'placeholder': 'Opcional — contexto para a decisão'}
        ),
    )


class DecisionForm(forms.Form):
    comment = forms.CharField(
        label='Comentário',
        required=False,
        widget=forms.Textarea(
            attrs={'rows': 3, 'class': 'wf-textarea', 'placeholder': 'Opcional — contexto para a decisão'}
        ),
    )
    signer_name = forms.CharField(
        label='Nome do signatário',
        required=True,
        max_length=160,
        widget=forms.TextInput(
            attrs={
                'class': 'wf-select',
                'placeholder': 'Digite seu nome completo para validar a assinatura',
                'autocomplete': 'name',
            }
        ),
    )
    confirm_read = forms.BooleanField(
        label='Declaro que revisei o conteúdo e confirmo esta decisão no sistema.',
        required=True,
    )
    confirm_phrase = forms.CharField(
        label='Frase de confirmação',
        required=True,
        max_length=20,
        widget=forms.TextInput(
            attrs={
                'class': 'wf-select',
                'placeholder': 'Digite APROVAR ou REPROVAR',
                'autocomplete': 'off',
            }
        ),
    )

    def validate_for_action(self, *, action: str, user, process_id: int) -> None:
        expected_action = 'APROVAR' if action == 'approve' else 'REPROVAR'
        expected = f'{expected_action} #{process_id}'
        phrase = (self.cleaned_data.get('confirm_phrase') or '').strip().upper()
        if phrase != expected:
            self.add_error('confirm_phrase', f'Digite exatamente "{expected}" para confirmar.')

        entered = (self.cleaned_data.get('signer_name') or '').strip().lower()
        expected_names = {
            (user.get_full_name() or '').strip().lower(),
            (getattr(user, 'username', '') or '').strip().lower(),
        }
        expected_names = {x for x in expected_names if x}
        if entered not in expected_names:
            self.add_error(
                'signer_name',
                'Use seu nome de utilizador autenticado (nome completo ou username).',
            )


class NewFlowForm(forms.Form):
    """Cria combinação projeto + categoria (fluxo vazio a ser preenchido no Admin)."""

    project = forms.ModelChoiceField(
        label='Obra (projeto)',
        queryset=Project.objects.filter(is_active=True).order_by('name'),
        widget=forms.Select(attrs={'class': 'wf-select'}),
    )
    category = forms.ModelChoiceField(
        label='Categoria',
        queryset=ProcessCategory.objects.filter(is_active=True).exclude(code='bm'),
        widget=forms.Select(attrs={'class': 'wf-select'}),
    )

    def clean(self):
        cleaned = super().clean()
        if not cleaned:
            return cleaned
        from workflow_aprovacao.models import ApprovalFlowDefinition

        if ApprovalFlowDefinition.objects.filter(
            project=cleaned['project'],
            category=cleaned['category'],
        ).exists():
            raise ValidationError('Já existe um fluxo para esta obra e categoria.')
        return cleaned
