from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import Insumo, ItemMapa, AlocacaoRecebimento
from obras.models import Obra, LocalObra


class SiengeImportUploadForm(forms.Form):
    """
    Upload do arquivo exportado do Sienge (CSV/Excel) para importar no sistema.
    """
    arquivo = forms.FileField(
        required=True,
        help_text='Envie o arquivo exportado do Sienge (.csv ou .xlsx).'
    )

    def clean_arquivo(self):
        f = self.cleaned_data['arquivo']
        name = (getattr(f, 'name', '') or '').lower()
        if not (name.endswith('.csv') or name.endswith('.xlsx') or name.endswith('.xls')):
            raise ValidationError('Formato inválido. Envie um .csv ou .xlsx/.xls.')
        # Limite simples de segurança (25MB)
        if getattr(f, 'size', 0) and f.size > 25 * 1024 * 1024:
            raise ValidationError('Arquivo muito grande (limite 25MB).')
        return f


class InsumoForm(forms.ModelForm):
    """
    Formulário para criar/editar insumo.
    
    NOTA: Insumos normalmente são importados do Sienge via CSV.
    Este formulário é para criação manual quando necessário.
    """
    
    UNIDADE_CHOICES = [
        ('UND', 'UND (Unidade)'),
        ('KG', 'KG (Quilograma)'),
        ('M', 'M (Metro)'),
        ('M²', 'M² (Metro Quadrado)'),
        ('M³', 'M³ (Metro Cúbico)'),
        ('L', 'L (Litro)'),
        ('TON', 'TON (Tonelada)'),
        ('PC', 'PC (Peça)'),
        ('CX', 'CX (Caixa)'),
        ('SACO', 'SACO'),
        ('ROL', 'ROL (Rolo)'),
    ]
    
    unidade = forms.ChoiceField(
        choices=UNIDADE_CHOICES,
        initial='UND',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = Insumo
        fields = ['codigo_sienge', 'descricao', 'unidade']
        widgets = {
            'codigo_sienge': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 5926, 16085',
                'required': True
            }),
            'descricao': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: CIMENTO PORTLAND COMPOSTO CP II-32',
                'required': True
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['codigo_sienge'].label = 'Código Sienge'
        self.fields['codigo_sienge'].help_text = 'Código do insumo no Sienge (ex: 5926)'
        self.fields['descricao'].label = 'Descrição'
        self.fields['descricao'].help_text = 'Descrição do insumo (como vem no Sienge)'
        self.fields['unidade'].label = 'Unidade'
        self.fields['unidade'].help_text = 'Unidade de medida'
    
    def clean_codigo_sienge(self):
        codigo = self.cleaned_data.get('codigo_sienge', '').strip()
        if not codigo:
            raise forms.ValidationError('Código Sienge é obrigatório')
        
        # Verificar se já existe (exceto se estiver editando o mesmo)
        qs = Insumo.objects.filter(codigo_sienge=codigo)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise forms.ValidationError(
                f'Insumo com código "{codigo}" já existe. Use outro código ou selecione o insumo existente.'
            )
        
        return codigo
    
    def clean_descricao(self):
        descricao = self.cleaned_data.get('descricao', '').strip()
        if not descricao:
            raise forms.ValidationError('Descrição é obrigatória')
        return descricao


class ItemMapaForm(forms.ModelForm):
    """Formulário para criar/editar item do mapa."""

    categoria = forms.ChoiceField(choices=ItemMapa.CATEGORIA_CHOICES, required=True)
    
    class Meta:
        model = ItemMapa
        fields = [
            'obra', 'insumo', 'categoria', 'local_aplicacao', 'responsavel',
            'prazo_necessidade', 'quantidade_planejada', 'prioridade',
            'observacao_eng', 'descricao_override', 'numero_sc'
        ]
        widgets = {
            'obra': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'insumo': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'categoria': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'local_aplicacao': forms.Select(attrs={'class': 'form-select'}),
            'responsavel': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome do responsável técnico'
            }),
            'prazo_necessidade': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'quantidade_planejada': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'required': True
            }),
            'prioridade': forms.Select(attrs={'class': 'form-select'}),
            'observacao_eng': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Observações adicionais'
            }),
            'descricao_override': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Descrição alternativa (opcional)'
            }),
            'numero_sc': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nº Solicitação (opcional)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        obra_id = kwargs.pop('obra_id', None)
        super().__init__(*args, **kwargs)
        
        self._obra_id = obra_id  # Guardar para validação
        
        # Filtrar obras ativas
        self.fields['obra'].queryset = Obra.objects.filter(ativa=True).order_by('nome')
        
        # Se obra_id foi passado, pré-selecionar e desabilitar mudança
        if obra_id:
            try:
                obra_obj = Obra.objects.get(id=obra_id, ativa=True)
                self.fields['obra'].initial = obra_obj
                # SEGREGAÇÃO: Filtrar locais APENAS da obra da sessão
                self.fields['local_aplicacao'].queryset = LocalObra.objects.filter(
                    obra_id=obra_id
                ).order_by('tipo', 'nome')
            except Obra.DoesNotExist:
                self.fields['local_aplicacao'].queryset = LocalObra.objects.none()
        else:
            self.fields['local_aplicacao'].queryset = LocalObra.objects.none()
            self.fields['local_aplicacao'].required = False
        
        # Filtrar insumos ativos
        self.fields['insumo'].queryset = Insumo.objects.filter(ativo=True).order_by('descricao')

        # Se item antigo tiver categoria fora da lista, incluir como opção "LEGADO" para não quebrar edição via form
        try:
            atual = (self.instance.categoria or '').strip()
        except Exception:
            atual = ''
        if atual and atual not in [v for v, _ in ItemMapa.CATEGORIA_CHOICES]:
            self.fields['categoria'].choices = [(atual, f'LEGADO: {atual}')] + list(self.fields['categoria'].choices)
    
    def clean(self):
        cleaned_data = super().clean()
        obra = cleaned_data.get('obra')
        insumo = cleaned_data.get('insumo')
        categoria = (cleaned_data.get('categoria') or '').strip()
        local_aplicacao = cleaned_data.get('local_aplicacao')

        # Categoria: lista fechada
        categorias_validas = {v for v, _ in ItemMapa.CATEGORIA_CHOICES}
        if categoria and categoria not in categorias_validas:
            raise ValidationError({'categoria': 'Categoria inválida. Selecione uma opção da lista.'})
        
        # SEGREGAÇÃO ESTRITA: Validar que local pertence à obra
        if local_aplicacao and obra:
            if local_aplicacao.obra_id != obra.id:
                raise ValidationError({
                    'local_aplicacao': f'Este local pertence a outra obra ({local_aplicacao.obra.nome}). '
                                       f'Selecione um local da obra {obra.nome}.'
                })
        
        # Verificar se já existe item com mesma obra + insumo + categoria + local
        # IMPORTANTE: Permite múltiplos itens com mesma obra+insumo+categoria desde que tenham locais diferentes
        # Isso permite dividir um insumo entre múltiplos locais (ex: Bloco A e Bloco B)
        if obra and insumo and categoria:
            qs = ItemMapa.objects.filter(
                obra=obra,
                insumo=insumo,
                categoria=categoria
            )
            # Se tem local, verificar duplicata apenas no mesmo local
            # Se não tem local, verificar se já existe item sem local
            if local_aplicacao:
                qs = qs.filter(local_aplicacao=local_aplicacao)
            else:
                qs = qs.filter(local_aplicacao__isnull=True)
            
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                if local_aplicacao:
                    raise ValidationError(
                        f'Item já existe para esta obra, insumo, categoria e local ({local_aplicacao.nome}).'
                    )
                else:
                    raise ValidationError(
                        f'Item já existe para esta obra, insumo e categoria (sem local definido).'
                    )
        
        return cleaned_data
    
    def clean_quantidade_planejada(self):
        quantidade = self.cleaned_data.get('quantidade_planejada')
        if quantidade and quantidade < 0:
            raise ValidationError('Quantidade não pode ser negativa')
        return quantidade or Decimal('0.00')


class AlocacaoRecebimentoForm(forms.ModelForm):
    """Formulário para alocar recebimento."""
    
    class Meta:
        model = AlocacaoRecebimento
        fields = ['local_aplicacao', 'quantidade_alocada']
        widgets = {
            'local_aplicacao': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'quantidade_alocada': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'required': True
            }),
        }
    
    def __init__(self, *args, **kwargs):
        obra = kwargs.pop('obra', None)
        item_mapa = kwargs.pop('item_mapa', None)
        super().__init__(*args, **kwargs)
        
        self.obra = obra
        self.item_mapa = item_mapa
        
        # Filtrar locais por obra
        if obra:
            self.fields['local_aplicacao'].queryset = LocalObra.objects.filter(
                obra=obra
            ).order_by('tipo', 'nome')
        else:
            self.fields['local_aplicacao'].queryset = LocalObra.objects.none()
    
    def clean_quantidade_alocada(self):
        quantidade = self.cleaned_data.get('quantidade_alocada')
        
        if not self.item_mapa:
            return quantidade
        
        # Validar se não excede quantidade recebida
        if quantidade > self.item_mapa.quantidade_recebida:
            raise ValidationError(
                f'Quantidade alocada ({quantidade}) excede o recebido '
                f'({self.item_mapa.quantidade_recebida}).'
            )
        
        return quantidade
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.obra:
            instance.obra = self.obra
        if self.item_mapa:
            instance.item_mapa = self.item_mapa
            instance.insumo = self.item_mapa.insumo
        
        if commit:
            instance.save()
        return instance

