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
