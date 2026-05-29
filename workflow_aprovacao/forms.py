import json

from django import forms
from django.core.exceptions import ValidationError

from core.models import Project
from workflow_aprovacao.models import ProcessCategory

_SIGNATURE_PREFIX = 'data:image/png;base64,'
_SIGNATURE_MIN_LEN = 500


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
    signature_data = forms.CharField(
        label='Assinatura manual',
        required=True,
        widget=forms.HiddenInput(attrs={'id': 'id_signature_data'}),
    )
    geolocation_data = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_geolocation_data'}),
    )

    def clean_signature_data(self):
        data = (self.cleaned_data.get('signature_data') or '').strip()
        if not data.startswith(_SIGNATURE_PREFIX):
            raise ValidationError('Desenhe sua assinatura no quadro acima ou use «Usar última assinatura».')
        if len(data) < _SIGNATURE_MIN_LEN:
            raise ValidationError('Assinatura vazia ou inválida. Desenhe novamente no quadro.')
        return data

    def clean_geolocation_data(self):
        raw = (self.cleaned_data.get('geolocation_data') or '').strip()
        if not raw:
            raise ValidationError('Ative a localização para assinar este processo.')
        try:
            payload = json.loads(raw)
        except Exception:
            raise ValidationError('Não foi possível validar a localização. Tente ativar novamente.')
        if not isinstance(payload, dict):
            raise ValidationError('Formato de localização inválido.')
        try:
            lat = float(payload.get('latitude'))
            lng = float(payload.get('longitude'))
        except (TypeError, ValueError):
            raise ValidationError('Localização inválida. Permita o acesso à localização do navegador.')
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise ValidationError('Coordenadas fora do intervalo permitido.')
        return raw

    def validate_for_action(self, *, action: str, user, process_id: int) -> None:
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


class ManualRequestForm(forms.Form):
    """Abertura manual genérica de processo por categoria."""

    project = forms.ModelChoiceField(
        label='Obra',
        queryset=Project.objects.filter(is_active=True).order_by('code'),
        widget=forms.Select(attrs={'class': 'wf-select'}),
    )
    category = forms.ModelChoiceField(
        label='Categoria',
        queryset=ProcessCategory.objects.filter(is_active=True).order_by('sort_order', 'name'),
        widget=forms.Select(attrs={'class': 'wf-select', 'id': 'id_manual_category'}),
    )
    title = forms.CharField(
        label='Título do pedido',
        max_length=300,
        widget=forms.TextInput(attrs={'class': 'wf-select', 'placeholder': 'Ex.: Contrato fornecedor XPTO'}),
    )
    summary = forms.CharField(
        label='Resumo',
        required=False,
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'wf-textarea'}),
    )
    notes = forms.CharField(
        label='Observações internas',
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'wf-textarea'}),
    )
    amount = forms.DecimalField(
        label='Valor (quando aplicável)',
        required=False,
        max_digits=14,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'wf-select', 'step': '0.01', 'placeholder': '0,00'}),
    )
    vendor_name = forms.CharField(
        label='Fornecedor / terceirizada',
        required=False,
        max_length=180,
        widget=forms.TextInput(attrs={'class': 'wf-select'}),
    )
    category_payload_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_category_payload_json'}),
    )

    def clean_category_payload_json(self):
        import json

        raw = (self.cleaned_data.get('category_payload_json') or '').strip()
        if not raw:
            return '{}'
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError('Dados dinâmicos inválidos.') from exc
        if not isinstance(data, dict):
            raise ValidationError('Dados dinâmicos inválidos.')
        return raw


class ExternalSignupReviewForm(forms.Form):
    action = forms.ChoiceField(
        choices=(('approve', 'Aprovar'), ('reject', 'Rejeitar')),
        widget=forms.HiddenInput(),
    )
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'wf-textarea', 'placeholder': 'Motivo (rejeição/cancelamento)'}),
    )

