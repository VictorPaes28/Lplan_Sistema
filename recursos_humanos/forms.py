from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import Colaborador, DocumentoColaborador, ObraLocal, TipoDocumento


class NovaRequisicaoForm(forms.Form):
    nome = forms.CharField(max_length=200, label='Nome completo')
    cpf = forms.CharField(max_length=14, label='CPF')
    cargo = forms.CharField(max_length=120, label='Cargo')
    obra = forms.ModelChoiceField(queryset=ObraLocal.objects.none(), label='Obra')
    tipo_contrato = forms.ChoiceField(
        choices=[
            ('CLT', 'CLT'),
            ('Temporário', 'Temporário'),
            ('Estágio', 'Estágio'),
            ('Pessoa Jurídica', 'Pessoa Jurídica'),
        ],
        initial='CLT',
    )
    salario = forms.CharField(max_length=40, label='Salário')
    data_inicio = forms.DateField(label='Data prevista de início', widget=forms.DateInput(attrs={'type': 'date'}))
    gestor = forms.CharField(max_length=120, label='Gestor aprovador')
    motivo = forms.ChoiceField(
        choices=[
            ('Nova contratação', 'Nova contratação'),
            ('Substituição', 'Substituição'),
            ('Expansão de equipe', 'Expansão de equipe'),
            ('Projeto específico', 'Projeto específico'),
        ],
    )
    observacoes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['obra'].queryset = ObraLocal.objects.all()
        for name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.Textarea, forms.Select, forms.DateInput)):
                field.widget.attrs.setdefault('class', 'rh-input')


class TipoDocumentoForm(forms.ModelForm):
    class Meta:
        model = TipoDocumento
        fields = ('nome', 'aplica_a', 'tem_validade', 'dias_validade', 'obrigatorio', 'ordem')
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'rh-input'}),
            'aplica_a': forms.Select(attrs={'class': 'rh-select'}),
            'dias_validade': forms.NumberInput(attrs={'min': 1, 'class': 'rh-input'}),
            'ordem': forms.NumberInput(attrs={'min': 0, 'class': 'rh-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('tem_validade') and not cleaned.get('dias_validade'):
            self.add_error('dias_validade', 'Informe os dias de validade.')
        return cleaned


class DocumentoStatusForm(forms.Form):
    status = forms.ChoiceField(choices=DocumentoColaborador.Status.choices)
    observacao = forms.CharField(required=False, max_length=300)


class DevolverAdmissaoForm(forms.Form):
    motivo = forms.CharField(max_length=300, label='Motivo da devolução')


class ColaboradorBasicoForm(forms.ModelForm):
    class Meta:
        model = Colaborador
        fields = (
            'nome', 'cpf', 'rg', 'cargo', 'empresa', 'endereco', 'dados_bancarios',
            'pis', 'escolaridade', 'tamanho_camisa', 'tamanho_bota', 'data_nascimento',
        )
        widgets = {
            'data_nascimento': forms.DateInput(attrs={'type': 'date', 'class': 'rh-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'rh-input'


class DocumentoUploadForm(forms.Form):
    arquivo = forms.FileField()

    def clean_arquivo(self):
        f = self.cleaned_data['arquivo']
        if f.size > 10 * 1024 * 1024:
            raise forms.ValidationError('Arquivo muito grande (máx. 10 MB).')
        return f
