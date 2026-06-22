import re

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import CargoRH, Colaborador, DocumentoColaborador, ObraLocal, PapelFluxoAdmissao, PrazoContrato, TipoDocumento
from .services.admissao import formatar_salario_br
from .services.admissao_actions import obras_reais_queryset

TIPO_CONTRATO_CHOICES = [
    ('CLT', 'CLT'),
    ('Temporário', 'Temporário'),
    ('Estágio', 'Estágio'),
    ('Pessoa Jurídica', 'Pessoa Jurídica'),
]

MAPA_TIPO_PRAZO = {
    'Temporário': 'determinado',
    'Estágio': 'estagio',
    'Pessoa Jurídica': 'pj',
}

DEFAULT_DURACAO_POR_TIPO_CONTRATO = {
    'Temporário': 180,
    'Estágio': 365,
    'Pessoa Jurídica': 365,
}

LIMITES_LEGAIS = {
    'determinado': (
        730,
        'Contrato por prazo determinado não pode exceder 2 anos (CLT art. 445).',
    ),
    'estagio': (
        730,
        'Estágio não pode exceder 2 anos (Lei 11.788/2008, art. 11).',
    ),
}

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
    email = forms.EmailField(label='E-mail', required=False)
    telefone = forms.CharField(max_length=20, label='Telefone')
    rg = forms.CharField(max_length=20, required=False, label='RG')
    data_nascimento = forms.DateField(
        required=False,
        label='Data de nascimento',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    pis = forms.CharField(max_length=20, required=False, label='PIS')
    endereco = forms.CharField(max_length=300, required=False, label='Endereço')
    dados_bancarios = forms.CharField(max_length=200, required=False, label='Conta bancária')
    escolaridade = forms.ChoiceField(
        choices=ESCOLARIDADE_CHOICES,
        required=False,
        label='Escolaridade',
    )
    tamanho_camisa = forms.CharField(max_length=10, required=False, label='Tam. camisa')
    tamanho_bota = forms.CharField(max_length=10, required=False, label='Tam. bota')
    empresa = forms.CharField(max_length=200, required=False, label='Empresa responsável')
    cargo = forms.CharField(max_length=120, label='Cargo')
    cargo_rh = forms.ModelChoiceField(
        queryset=CargoRH.objects.none(),
        required=True,
        label='Cargo (RH)',
        error_messages={'required': 'Selecione o cargo (RH).'},
    )
    obra = forms.ModelMultipleChoiceField(
        queryset=ObraLocal.objects.none(),
        label='Obras',
        widget=forms.CheckboxSelectMultiple(),
    )
    aprovadores = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        label='Aprovadores da requisição',
        widget=forms.CheckboxSelectMultiple(),
        error_messages={'required': 'Selecione ao menos um aprovador.'},
    )
    tipo_contrato = forms.ChoiceField(
        choices=TIPO_CONTRATO_CHOICES,
        initial='CLT',
    )
    salario = forms.CharField(max_length=40, label='Salário')
    deslocamento_origem = forms.CharField(
        max_length=120,
        required=False,
        label='Cidade de origem (de onde vem)',
    )
    deslocamento_destino = forms.CharField(
        max_length=120,
        required=False,
        label='Cidade de destino (para onde vai)',
    )
    reembolsos_json = forms.CharField(required=False, widget=forms.HiddenInput())
    data_inicio = forms.DateField(label='Data prevista de início', widget=forms.DateInput(attrs={'type': 'date'}))
    motivo = forms.ChoiceField(
        choices=[
            ('Nova contratação', 'Nova contratação'),
            ('Substituição', 'Substituição'),
            ('Expansão de equipe', 'Expansão de equipe'),
            ('Projeto específico', 'Projeto específico'),
        ],
    )
    observacoes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))
    prazo_duracao_dias = forms.IntegerField(
        required=False,
        label='Duração do contrato (dias)',
        min_value=1,
    )

    def __init__(self, *args, colaborador_pk=None, **kwargs):
        self.colaborador_pk = colaborador_pk
        super().__init__(*args, **kwargs)
        self.fields['obra'].queryset = obras_reais_queryset()
        self.fields['obra'].widget.attrs.setdefault('class', 'rh-checkbox-list')
        self.fields['aprovadores'].queryset = User.objects.filter(
            is_active=True,
        ).order_by('first_name', 'last_name', 'username')
        self.fields['aprovadores'].widget.attrs.setdefault('class', 'rh-checkbox-list')
        self.fields['cargo_rh'].queryset = CargoRH.objects.all()
        self.fields['cargo_rh'].empty_label = 'Selecione o cargo (RH)'
        for name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.Textarea, forms.DateInput)):
                field.widget.attrs.setdefault('class', 'rh-input')
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault('class', 'rh-select')
        self.fields['observacoes'].widget.attrs.setdefault('class', 'rh-input rh-textarea')
        self.fields['prazo_duracao_dias'].widget.attrs.setdefault('class', 'rh-input')
        self.fields['escolaridade'].widget.attrs.setdefault('class', 'rh-select')
        self.fields['data_nascimento'].widget.attrs.setdefault('class', 'rh-input')

    def get_tipo_prazo(self):
        if not self.tem_prazo():
            return None
        tipo_contrato = self.cleaned_data.get('tipo_contrato')
        return MAPA_TIPO_PRAZO.get(tipo_contrato)

    def tem_prazo(self):
        if self.cleaned_data.get('tipo_contrato') == 'CLT':
            return False
        duracao = self.cleaned_data.get('prazo_duracao_dias')
        return bool(duracao and duracao > 0)

    def clean(self):
        cleaned = super().clean()
        tipo_contrato = cleaned.get('tipo_contrato')

        if tipo_contrato == 'CLT':
            cleaned['prazo_duracao_dias'] = None

        elif tipo_contrato == 'Estágio':
            duracao = cleaned.get('prazo_duracao_dias') or DEFAULT_DURACAO_POR_TIPO_CONTRATO['Estágio']
            cleaned['prazo_duracao_dias'] = duracao
            limite, msg_erro = LIMITES_LEGAIS['estagio']
            if duracao > limite:
                self.add_error('prazo_duracao_dias', msg_erro)

        elif tipo_contrato and tipo_contrato != 'CLT' and not cleaned.get('prazo_duracao_dias'):
            cleaned['prazo_duracao_dias'] = DEFAULT_DURACAO_POR_TIPO_CONTRATO.get(tipo_contrato)

        from recursos_humanos.services.reembolsos import parse_reembolsos_json

        cleaned['reembolsos'] = parse_reembolsos_json(cleaned.pop('reembolsos_json', '') or '[]')

        return cleaned

    def clean_email(self):
        return (self.cleaned_data.get('email') or '').strip()

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

class TipoDocumentoCatalogoForm(forms.ModelForm):
    """Catálogo: escopo (todos/por cargo) vem do botão de abertura; vínculos na aba Por cargo."""

    class Meta:
        model = TipoDocumento
        fields = (
            'nome', 'categoria', 'instrucoes_portal', 'aplica_a',
            'tem_validade', 'dias_validade', 'obrigatorio', 'ativo',
        )
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'rh-input'}),
            'categoria': forms.Select(attrs={'class': 'rh-select'}),
            'instrucoes_portal': forms.TextInput(attrs={'class': 'rh-input'}),
            'aplica_a': forms.HiddenInput(),
            'tem_validade': forms.CheckboxInput(attrs={'class': 'rh-docconfig-tem-validade'}),
            'obrigatorio': forms.CheckboxInput(attrs={'class': 'rh-docconfig-obrigatorio'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'rh-docconfig-ativo'}),
            'dias_validade': forms.NumberInput(attrs={
                'min': 1,
                'class': 'rh-input rh-docconfig-dias-validade',
            }),
        }
        labels = {
            'instrucoes_portal': 'Instruções para o candidato',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categoria'].choices = TipoDocumento.Categoria.choices
        if not self.instance.pk:
            self.fields['dias_validade'].initial = 365
            self.fields['obrigatorio'].initial = True
            self.fields['ativo'].initial = True
            self.fields['aplica_a'].initial = TipoDocumento.AplicaA.TODOS

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('tem_validade') and not cleaned.get('dias_validade'):
            self.add_error('dias_validade', 'Informe os dias de validade.')
        elif not cleaned.get('tem_validade'):
            cleaned['dias_validade'] = None
        if self.instance.pk:
            cleaned['aplica_a'] = self.instance.aplica_a
        elif not self.instance.pk:
            # Checkbox ausente no POST = desmarcado no Django; manter padrão do catálogo.
            if 'ativo' not in self.data:
                cleaned['ativo'] = True
            if 'obrigatorio' not in self.data:
                cleaned['obrigatorio'] = True
            cat = cleaned.get('categoria') or TipoDocumento.Categoria.OUTROS
            nome = (cleaned.get('nome') or '').strip()
            if cat == TipoDocumento.Categoria.OUTROS and nome:
                from recursos_humanos.services.admissao import _categoria_documento_por_nome

                cleaned['categoria'] = _categoria_documento_por_nome(nome)
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not self.instance.pk:
            from django.db.models import Max
            max_ordem = TipoDocumento.objects.aggregate(m=Max('ordem'))['m'] or 0
            instance.ordem = max_ordem + 1
        if commit:
            instance.save()
            if instance.aplica_a != TipoDocumento.AplicaA.POR_CARGO:
                instance.cargos_aplicaveis.clear()
            if instance.aplica_a != TipoDocumento.AplicaA.POR_OBRA:
                instance.obras_aplicaveis.clear()
        return instance


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
            'nome', 'cpf', 'email', 'telefone', 'rg', 'cargo', 'cargo_rh', 'empresa', 'endereco', 'dados_bancarios',
            'pis', 'escolaridade', 'tamanho_camisa', 'tamanho_bota', 'data_nascimento',
            'tipo_contrato', 'salario', 'deslocamento_origem', 'deslocamento_destino',
            'data_admissao', 'status', 'observacoes_requisicao', 'obras',
        )
        widgets = {
            'data_nascimento': forms.DateInput(attrs={'type': 'date', 'class': 'rh-input'}),
            'data_admissao': forms.DateInput(attrs={'type': 'date', 'class': 'rh-input'}),
            'tipo_contrato': forms.Select(attrs={'class': 'rh-select'}),
            'status': forms.Select(attrs={'class': 'rh-select'}),
            'cargo_rh': forms.Select(attrs={'class': 'rh-select'}),
            'observacoes_requisicao': forms.Textarea(attrs={'class': 'rh-input rh-textarea', 'rows': 3}),
            'obras': forms.CheckboxSelectMultiple(attrs={'class': 'rh-checkbox-list'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .services.admissao_actions import obras_reais_queryset
        from .services.prazo_contrato import (
            data_admissao_oficial_bloqueada,
            obter_data_admissao_oficial,
        )

        self.fields['obras'].queryset = obras_reais_queryset()
        self.fields['obras'].required = False
        self.fields['cargo_rh'].queryset = CargoRH.objects.all()
        self.fields['cargo_rh'].required = False
        self.fields['cargo_rh'].empty_label = '— Nenhum —'
        self.fields['tipo_contrato'].widget = forms.Select(
            choices=TIPO_CONTRATO_CHOICES,
            attrs={'class': 'rh-select'},
        )
        self.fields['status'].choices = Colaborador.Status.choices
        if self.instance and self.instance.pk:
            if data_admissao_oficial_bloqueada(self.instance):
                oficial = obter_data_admissao_oficial(self.instance)
                self.fields['data_admissao'].disabled = True
                self.fields['data_admissao'].help_text = (
                    f'Data oficial da etapa 4: {oficial:%d/%m/%Y}. '
                    'Altere somente no fluxo de admissão (etapa do contrato).'
                )
        for name, field in self.fields.items():
            if name in ('obras', 'cargo_rh'):
                continue
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'rh-input'

    def clean_cpf(self):
        exclude_pk = self.instance.pk if self.instance and self.instance.pk else None
        return normalizar_cpf(self.cleaned_data.get('cpf'), exclude_pk=exclude_pk)

    def clean(self):
        cleaned = super().clean()
        if not self.instance or not self.instance.pk:
            return cleaned
        from .services.prazo_contrato import (
            data_admissao_oficial_bloqueada,
            obter_data_admissao_oficial,
        )

        if data_admissao_oficial_bloqueada(self.instance):
            cleaned['data_admissao'] = obter_data_admissao_oficial(self.instance)
        return cleaned


class ConfigurarAlertasForm(forms.Form):
    dias_antecedencia_documentos = forms.IntegerField(
        min_value=1,
        max_value=365,
        label='Documentos e prazos de contrato — avisar com antecedência',
    )
    dias_renotificar_vencidos = forms.IntegerField(
        min_value=1,
        max_value=90,
        label='Documentos vencidos — renotificar a cada',
    )
    notificar_email = forms.BooleanField(required=False, label='E-mail para os responsáveis')
    notificar_sistema = forms.BooleanField(required=False, label='Notificação no sistema')
    responsaveis = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        label='Responsáveis',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from recursos_humanos.services.alertas_config import usuarios_staff_alertas

        self.fields['responsaveis'].queryset = usuarios_staff_alertas()


PORTAL_UPLOAD_MAX_MB = 50
PORTAL_UPLOAD_MAX_BYTES = PORTAL_UPLOAD_MAX_MB * 1024 * 1024


def mensagem_erros_upload(form: 'DocumentoUploadForm') -> str:
    """Primeira mensagem útil do formulário de upload (evita culpar o tamanho à toa)."""
    if form.errors.get('arquivo'):
        return str(form.errors['arquivo'][0])
    if form.errors.get('data_emissao'):
        return str(form.errors['data_emissao'][0])
    if form.non_field_errors():
        return str(form.non_field_errors()[0])
    return 'Verifique o arquivo selecionado e a data de emissão, se solicitada.'


class DocumentoUploadForm(forms.Form):
    arquivo = forms.FileField()
    data_emissao = forms.DateField(
        label='Data de emissão do documento',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'rh-input'}),
        help_text='Necessário para documentos com validade',
    )

    def __init__(self, *args, requer_emissao: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.requer_emissao = requer_emissao
        if requer_emissao:
            self.fields['data_emissao'].required = True

    def clean_arquivo(self):
        f = self.cleaned_data['arquivo']
        if f.size > PORTAL_UPLOAD_MAX_BYTES:
            raise ValidationError(f'Arquivo muito grande (máx. {PORTAL_UPLOAD_MAX_MB} MB).')
        return f

    def clean(self):
        cleaned = super().clean()
        if self.requer_emissao and not cleaned.get('data_emissao'):
            self.add_error('data_emissao', 'Informe a data de emissão do documento.')
        return cleaned


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


class PapelFluxoAdmissaoForm(forms.ModelForm):
    usuarios = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True).order_by(
            'first_name', 'last_name', 'username',
        ),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'rh-checkbox-list rh-papel-user-list'}),
        label='',
    )

    class Meta:
        model = PapelFluxoAdmissao
        fields = ('usuarios',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['usuarios'].label_from_instance = self._rotulo_usuario

    @staticmethod
    def _rotulo_usuario(user):
        nome = (user.get_full_name() or '').strip()
        if nome:
            return f'{nome} ({user.username})'
        return user.username
