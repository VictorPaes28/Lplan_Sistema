"""Formulários da gestão do catálogo de mão de obra por obra."""
from django import forms

from .models import ProjectLaborCategory, ProjectLaborItem


class ProjectLaborCategoryForm(forms.ModelForm):
    class Meta:
        model = ProjectLaborCategory
        fields = ['name', 'order', 'is_active']
        labels = {
            'name': 'Nome da categoria',
            'order': 'Posição na lista',
            'is_active': 'Mostrar no formulário do RDO',
        }
        help_texts = {
            'is_active': 'Desmarque para ocultar todos os cargos desta categoria no diário.',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'locais-input', 'maxlength': 100}),
            'order': forms.NumberInput(attrs={'class': 'locais-input', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'locais-checkbox'}),
        }


class ProjectLaborCategoryCreateForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        label='Nome da categoria',
        widget=forms.TextInput(attrs={'class': 'locais-input', 'placeholder': 'Ex.: Terceirizada local'}),
    )
    order = forms.IntegerField(
        required=False,
        min_value=0,
        label='Posição na lista (opcional)',
        widget=forms.NumberInput(attrs={'class': 'locais-input', 'placeholder': 'Automático'}),
    )


class ProjectLaborItemForm(forms.ModelForm):
    class Meta:
        model = ProjectLaborItem
        fields = ['name', 'category', 'order', 'is_active']
        labels = {
            'name': 'Nome do cargo',
            'category': 'Categoria',
            'order': 'Posição na lista',
            'is_active': 'Mostrar no formulário do RDO',
        }
        help_texts = {
            'is_active': 'Desmarque para ocultar só este cargo no diário.',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'locais-input', 'maxlength': 120}),
            'category': forms.Select(attrs={'class': 'locais-select'}),
            'order': forms.NumberInput(attrs={'class': 'locais-input', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'locais-checkbox'}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project is not None:
            self.fields['category'].queryset = ProjectLaborCategory.objects.filter(
                project=project
            ).order_by('order', 'name')


class ProjectLaborItemCreateForm(forms.Form):
    name = forms.CharField(
        max_length=120,
        label='Nome do cargo',
        widget=forms.TextInput(attrs={'class': 'locais-input', 'placeholder': 'Ex.: Montador de andaime'}),
    )
    category = forms.ModelChoiceField(
        queryset=ProjectLaborCategory.objects.none(),
        label='Categoria',
        widget=forms.Select(attrs={'class': 'locais-select'}),
    )
    order = forms.IntegerField(
        required=False,
        min_value=0,
        label='Posição na lista (opcional)',
        widget=forms.NumberInput(attrs={'class': 'locais-input', 'placeholder': 'Automático'}),
    )

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project is not None:
            self.fields['category'].queryset = ProjectLaborCategory.objects.filter(
                project=project
            ).order_by('order', 'name')
