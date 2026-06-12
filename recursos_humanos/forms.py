import re

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import CargoRH, Colaborador, DocumentoColaborador, ObraLocal, TipoDocumento
from .services.admissao import formatar_salario_br
from .services.admissao_actions import obras_reais_queryset, usuarios_gestor_list

TIPO_CONTRATO_CHOICES = [
    ('CLT', 'CLT'),
    ('Temporário', 'Temporário'),
    ('Estágio', 'Estágio'),
    ('Pessoa Jurídica', 'Pessoa Jurídica'),
]

ESCOLARIDADE_CHOICES = [
    ('', 'Selecione...'),
    ('Analfabeto', 'Analfabeto'),
    ('Alfabetizado sem instrução formal', 'Alfabetizado sem instrução formal'),
    ('Ensino fundamental incompleto', 'Ensino fundamental incompleto'),
    ('Ensino fundamental completo', 'Ensino fundamental completo'),
    ('Ensino médio incompleto', 'Ensino médio incompleto'),
    ('Ensino médio completo', 'Ensino médio completo'),
    ('Ensino técnico incompleto', 'Ensino técnico incompleto'),
    ('Ensino técnico completo', 'Ensino técnico completo'),
    ('Ensino superior incompleto', 'Ensino superior incompleto'),
    ('Ensino superior completo', 'Ensino superior completo'),
    ('Pós-graduação lato sensu', 'Pós-graduação lato sensu'),
    ('Pós-graduação stricto sensu — mestrado', 'Pós-graduação stricto sensu — mestrado'),
    ('Pós-graduação stricto sensu — doutorado', 'Pós-graduação stricto sensu — doutorado'),
    ('Pós-doutorado', 'Pós-doutorado'),
]


def normalizar_telefone(telefone_raw):
    telefone = re.sub(r'\D', '', (telefone_raw or '').strip())
    if len(telefone) < 10 or len(telefone) > 13:
        raise ValidationError('Informe um telefone válido com DDD.')
    return telefone


def normalizar_cpf(cpf_raw, *, exclude_pk=None):
    cpf = (cpf_raw or '').strip()
    cpf_numeros = re.sub(r'\D', '', cpf)
    if len(cpf_numeros) != 11:
        raise ValidationError('CPF deve ter 11 dígitos.')
    cpf_fmt = f'{cpf_numeros[:3]}.{cpf_numeros[3:6]}.{cpf_numeros[6:9]}-{cpf_numeros[9:]}'
    qs = Colaborador.objects.filter(cpf=cpf_fmt)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        raise ValidationError('CPF já cadastrado.')
    return cpf_fmt


class NovaRequisicaoForm(forms.Form):
    nome = forms.CharField(max_length=200, label='Nome completo')
    cpf = forms.CharField(max_length=14, label='CPF')
    email = forms.EmailField(label='E-mail')
    telefone = forms.CharField(max_length=20, label='Telefone')
    cargo = forms.CharField(max_length=120, label='Cargo')
    cargo_rh = forms.ModelChoiceField(
        queryset=CargoRH.objects.none(),
        required=False,
        label='Cargo (RH)',
    )
    obra = forms.ModelMultipleChoiceField(
        queryset=ObraLocal.objects.none(),
        label='Obras',
        widget=forms.CheckboxSelectMultiple(),
    )
    tipo_contrato = forms.ChoiceField(
        choices=TIPO_CONTRATO_CHOICES,
        initial='CLT',
    )
    salario = forms.CharField(max_length=40, label='Salário')
    data_inicio = forms.DateField(label='Data prevista de início', widget=forms.DateInput(attrs={'type': 'date'}))
    gestor_id = forms.IntegerField(label='Gestor responsável')
    motivo = forms.ChoiceField(
        choices=[
            ('Nova contratação', 'Nova contratação'),
            ('Substituição', 'Substituição'),
            ('Expansão de equipe', 'Expansão de equipe'),
            ('Projeto específico', 'Projeto específico'),
        ],
    )
    observacoes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, colaborador_pk=None, **kwargs):
        self.colaborador_pk = colaborador_pk
        super().__init__(*args, **kwargs)
        self.fields['obra'].queryset = obras_reais_queryset()
        self.fields['obra'].widget.attrs.setdefault('class', 'rh-checkbox-list')
        self.fields['cargo_rh'].queryset = CargoRH.objects.all()
        gestor_choices = [('', 'Selecione o gestor')]
        gestor_choices += [(u['id'], u['nome']) for u in usuarios_gestor_list()]
        self.fields['gestor_id'].widget = forms.Select(
            choices=gestor_choices,
            attrs={'class': 'rh-select'},
        )
        for name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.Textarea, forms.DateInput)):
                field.widget.attrs.setdefault('class', 'rh-input')
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault('class', 'rh-select')
        self.fields['observacoes'].widget.attrs.setdefault('class', 'rh-input rh-textarea')

    def clean_cpf(self):
        return normalizar_cpf(
            self.cleaned_data.get('cpf'),
            exclude_pk=self.colaborador_pk,
        )

    def clean_telefone(self):
        return normalizar_telefone(self.cleaned_data.get('telefone'))

    def clean_salario(self):
        return formatar_salario_br(self.cleaned_data.get('salario'))

    def clean_obra(self):
        obras = self.cleaned_data.get('obra')
        if not obras:
            raise ValidationError('Selecione ao menos uma obra.')
        return obras

    def clean_gestor_id(self):
        from django.contrib.auth.models import User

        gestor_id = self.cleaned_data.get('gestor_id')
        try:
            user = User.objects.get(pk=gestor_id, is_active=True)
        except User.DoesNotExist:
            raise ValidationError('Selecione um gestor válido do sistema.')
        self.cleaned_gestor_user = user
        return gestor_id


class TipoDocumentoForm(forms.ModelForm):
    class Meta:
        model = TipoDocumento
        fields = (
            'nome', 'aplica_a', 'cargos_aplicaveis', 'obras_aplicaveis',
            'tem_validade', 'dias_validade', 'obrigatorio',
        )
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'rh-input',
                'placeholder': 'Ex: CNH – Carteira de Habilitação',
            }),
            'aplica_a': forms.Select(attrs={'class': 'rh-select rh-aplica-a-select'}),
            'cargos_aplicaveis': forms.CheckboxSelectMultiple(attrs={'class': 'rh-checkbox-list'}),
            'obras_aplicaveis': forms.CheckboxSelectMultiple(attrs={'class': 'rh-checkbox-list'}),
            'tem_validade': forms.CheckboxInput(attrs={'class': 'rh-docconfig-tem-validade'}),
            'obrigatorio': forms.CheckboxInput(attrs={'class': 'rh-docconfig-obrigatorio'}),
            'dias_validade': forms.NumberInput(attrs={
                'min': 1,
                'class': 'rh-input rh-docconfig-dias-validade',
                'placeholder': '365',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cargos_aplicaveis'].queryset = CargoRH.objects.all()
        self.fields['obras_aplicaveis'].queryset = ObraLocal.objects.all()
        if not self.instance.pk:
            self.fields['dias_validade'].initial = 365
            self.fields['obrigatorio'].initial = True
        elif not self.instance.tem_validade and not self.instance.dias_validade:
            self.fields['dias_validade'].initial = 365

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('tem_validade'):
            if not cleaned.get('dias_validade'):
                self.add_error('dias_validade', 'Informe os dias de validade.')
        else:
            cleaned['dias_validade'] = None
        aplica_a = cleaned.get('aplica_a')
        if aplica_a == TipoDocumento.AplicaA.POR_CARGO and not cleaned.get('cargos_aplicaveis'):
            self.add_error('cargos_aplicaveis', 'Selecione ao menos um cargo.')
        if aplica_a == TipoDocumento.AplicaA.POR_OBRA and not cleaned.get('obras_aplicaveis'):
            self.add_error('obras_aplicaveis', 'Selecione ao menos uma obra.')
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.pk:
            from django.db.models import Max
            max_ordem = TipoDocumento.objects.aggregate(m=Max('ordem'))['m'] or 0
            instance.ordem = max_ordem + 1
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class CargoRHForm(forms.ModelForm):
    class Meta:
        model = CargoRH
        fields = ('nome',)
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'rh-input',
                'placeholder': 'Ex: Pedreiro',
            }),
        }


class DocumentoStatusForm(forms.Form):
    status = forms.ChoiceField(choices=DocumentoColaborador.Status.choices)
    observacao = forms.CharField(required=False, max_length=300)


class DocumentoRejeitarForm(forms.Form):
    observacao = forms.CharField(
        max_length=300,
        label='Observação para o candidato',
        widget=forms.Textarea(attrs={
            'class': 'rh-input rh-textarea',
            'rows': 3,
            'placeholder': 'Explique o que precisa ser corrigido ou reenviado...',
        }),
    )

    def clean_observacao(self):
        obs = (self.cleaned_data.get('observacao') or '').strip()
        if not obs:
            raise forms.ValidationError('Informe uma observação para o candidato.')
        return obs


class DevolverAdmissaoForm(forms.Form):
    motivo = forms.CharField(max_length=300, label='Motivo da devolução')


class ReprovarRequisicaoForm(forms.Form):
    motivo = forms.CharField(
        max_length=500,
        label='Motivo da reprovação',
        widget=forms.Textarea(attrs={'class': 'rh-input rh-textarea', 'rows': 4, 'placeholder': 'Descreva o que precisa ser corrigido...'}),
    )


class ColaboradorBasicoForm(forms.ModelForm):
    class Meta:
        model = Colaborador
        fields = (
            'nome', 'cpf', 'email', 'telefone', 'rg', 'cargo', 'empresa', 'endereco', 'dados_bancarios',
            'pis', 'escolaridade', 'tamanho_camisa', 'tamanho_bota', 'data_nascimento',
            'tipo_contrato', 'salario', 'data_admissao', 'status', 'observacoes_requisicao', 'obras',
        )
        widgets = {
            'data_nascimento': forms.DateInput(attrs={'type': 'date', 'class': 'rh-input'}),
            'data_admissao': forms.DateInput(attrs={'type': 'date', 'class': 'rh-input'}),
            'tipo_contrato': forms.Select(attrs={'class': 'rh-select'}),
            'status': forms.Select(attrs={'class': 'rh-select'}),
            'observacoes_requisicao': forms.Textarea(attrs={'class': 'rh-input rh-textarea', 'rows': 3}),
            'obras': forms.CheckboxSelectMultiple(attrs={'class': 'rh-checkbox-list'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .services.admissao_actions import obras_reais_queryset

        self.fields['obras'].queryset = obras_reais_queryset()
        self.fields['obras'].required = False
        self.fields['tipo_contrato'].widget = forms.Select(
            choices=TIPO_CONTRATO_CHOICES,
            attrs={'class': 'rh-select'},
        )
        self.fields['status'].choices = Colaborador.Status.choices
        for name, field in self.fields.items():
            if name == 'obras':
                continue
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'rh-input'

    def clean_cpf(self):
        exclude_pk = self.instance.pk if self.instance and self.instance.pk else None
        return normalizar_cpf(self.cleaned_data.get('cpf'), exclude_pk=exclude_pk)


class ConfigurarAlertasForm(forms.Form):
    dias_documento_vencendo = forms.IntegerField(min_value=1, max_value=365, label='Documentos com vencimento próximo')
    dias_treinamento_vencer = forms.IntegerField(min_value=1, max_value=365, label='Treinamentos a vencer')
    dias_renovacao_aso = forms.IntegerField(min_value=1, max_value=365, label='Renovação de ASO')
    dias_renotificar_vencido = forms.IntegerField(min_value=1, max_value=90, label='Documentos vencidos — renotificar')
    canal_email_rh = forms.BooleanField(required=False, label='E-mail para o RH')
    canal_notificacao_sistema = forms.BooleanField(required=False, label='Notificação no sistema')
    canal_whatsapp_gestor = forms.BooleanField(required=False, label='WhatsApp para o gestor responsável')
    canal_relatorio_pdf_semanal = forms.BooleanField(required=False, label='Relatório semanal em PDF por e-mail')
    responsaveis = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        label='Responsáveis',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from recursos_humanos.services.alertas_config import usuarios_elegiveis_alertas

        self.fields['responsaveis'].queryset = usuarios_elegiveis_alertas()


class DocumentoUploadForm(forms.Form):
    arquivo = forms.FileField()

    def clean_arquivo(self):
        f = self.cleaned_data['arquivo']
        if f.size > 10 * 1024 * 1024:
            raise ValidationError('Arquivo muito grande (máx. 10 MB).')
        return f


class PortalCandidatoDadosForm(forms.ModelForm):
    """Dados pessoais preenchidos pelo candidato no portal (não coletados na requisição)."""

    escolaridade = forms.ChoiceField(
        choices=ESCOLARIDADE_CHOICES,
        widget=forms.Select(attrs={'class': 'portal-select'}),
    )
    tamanho_camisa = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'portal-input',
            'placeholder': 'Ex: M, G, GG',
        }),
    )
    tamanho_bota = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'portal-input',
            'placeholder': 'Ex: 40, 41, 42',
        }),
    )

    class Meta:
        model = Colaborador
        fields = (
            'rg',
            'data_nascimento',
            'pis',
            'endereco',
            'dados_bancarios',
            'escolaridade',
            'tamanho_camisa',
            'tamanho_bota',
        )
        widgets = {
            'rg': forms.TextInput(attrs={'class': 'portal-input', 'placeholder': 'Ex: 1.234.567'}),
            'data_nascimento': forms.DateInput(attrs={'type': 'date', 'class': 'portal-input'}),
            'pis': forms.TextInput(attrs={'class': 'portal-input', 'placeholder': 'Número do PIS/PASEP'}),
            'endereco': forms.TextInput(attrs={
                'class': 'portal-input',
                'placeholder': 'Rua, número, bairro, cidade — UF',
            }),
            'dados_bancarios': forms.TextInput(attrs={
                'class': 'portal-input',
                'placeholder': 'Banco, agência, conta e tipo',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        obrigatorios = (
            'rg', 'data_nascimento', 'endereco', 'dados_bancarios',
            'escolaridade', 'tamanho_camisa', 'tamanho_bota',
        )
        for name in self.fields:
            self.fields[name].required = name in obrigatorios

    def clean_data_nascimento(self):
        from django.utils import timezone

        data = self.cleaned_data.get('data_nascimento')
        if data and data > timezone.localdate():
            raise ValidationError('Data de nascimento não pode ser no futuro.')
        return data
