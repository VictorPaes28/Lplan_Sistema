from django import forms
from django.contrib.auth.models import User, Group
from django.db.models import Q
from .models import Empresa, Obra, WorkOrder, Attachment, WorkOrderPermission


class EmpresaForm(forms.ModelForm):
    """
    Formulário para criar/editar Empresa.
    """
    
    class Meta:
        model = Empresa
        fields = [
            'codigo',
            'nome',
            'email',
            'telefone',
            'responsavel',
            'ativo',
        ]
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control'}),
            'responsavel': forms.Select(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filtrar usuários para o campo responsavel
        # Apenas usuários do grupo "Responsavel Empresa" ou Administradores
        from .utils import is_admin
        
        # Buscar grupo "Responsavel Empresa"
        try:
            grupo_responsavel = Group.objects.get(name='Responsavel Empresa')
            # Usuários do grupo Responsavel Empresa + Administradores + Superusers
            self.fields['responsavel'].queryset = User.objects.filter(
                Q(groups=grupo_responsavel) | Q(is_superuser=True) | Q(groups__name='Administrador')
            ).distinct().order_by('first_name', 'last_name', 'username')
        except Group.DoesNotExist:
            # Se o grupo não existir, mostrar apenas admins e superusers
            self.fields['responsavel'].queryset = User.objects.filter(
                Q(is_superuser=True) | Q(groups__name='Administrador')
            ).distinct().order_by('first_name', 'last_name', 'username')
        
        # Tornar o campo opcional (pode ser None)
        self.fields['responsavel'].required = False
    
    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo')
        if codigo:
            codigo = codigo.strip().upper()
            # Verificar unicidade (exceto se estiver editando a mesma empresa)
            empresa_existente = Empresa.objects.filter(codigo=codigo)
            if self.instance.pk:
                empresa_existente = empresa_existente.exclude(pk=self.instance.pk)
            if empresa_existente.exists():
                raise forms.ValidationError('Já existe uma empresa com este código.')
        return codigo


class ObraForm(forms.ModelForm):
    """
    Formulário para criar/editar Obra.
    """
    
    class Meta:
        model = Obra
        fields = [
            'empresa',
            'codigo',
            'nome',
            'descricao',
            'email_obra',
            'ativo',
        ]
        widgets = {
            'empresa': forms.Select(attrs={'class': 'form-control'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'email_obra': forms.EmailInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Tornar empresa obrigatória
        self.fields['empresa'].required = True
        
        # Filtrar empresas baseado no usuário
        if user:
            from .utils import is_responsavel_empresa, is_admin
            
            if is_responsavel_empresa(user) and not is_admin(user):
                # Responsáveis só veem empresas das quais são responsáveis
                self.fields['empresa'].queryset = Empresa.objects.filter(
                    responsavel=user,
                    ativo=True
                ).order_by('codigo')
            else:
                # Admins veem todas as empresas ativas
                self.fields['empresa'].queryset = Empresa.objects.filter(ativo=True).order_by('codigo')
        else:
            self.fields['empresa'].queryset = Empresa.objects.filter(ativo=True).order_by('codigo')
    
    def clean(self):
        cleaned_data = super().clean()
        empresa = cleaned_data.get('empresa')
        codigo = cleaned_data.get('codigo')
        
        # Validar que empresa é obrigatória
        if not empresa:
            raise forms.ValidationError({
                'empresa': 'É obrigatório selecionar uma empresa.'
            })
        
        # Validar unicidade do código por empresa
        if codigo and empresa:
            codigo = codigo.strip().upper()
            cleaned_data['codigo'] = codigo
            
            # Verificar unicidade por empresa (exceto se estiver editando a mesma obra)
            obra_existente = Obra.objects.filter(empresa=empresa, codigo=codigo)
            if self.instance.pk:
                obra_existente = obra_existente.exclude(pk=self.instance.pk)
            if obra_existente.exists():
                raise forms.ValidationError({
                    'codigo': f'Já existe uma obra com este código na empresa {empresa.nome}.'
                })
        
        return cleaned_data
    
    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo')
        if codigo:
            codigo = codigo.strip().upper()
        return codigo


class WorkOrderForm(forms.ModelForm):
    """
    Formulário para criar/editar WorkOrder.
    """
    
    class Meta:
        model = WorkOrder
        fields = [
            'obra',
            'codigo',
            'nome_credor',
            'tipo_solicitacao',
            'observacoes',
            'status',
            'valor_estimado',
            'prazo_estimado',
            'local',
        ]
        widgets = {
            'obra': forms.Select(attrs={'class': 'form-control'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'nome_credor': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_solicitacao': forms.Select(attrs={'class': 'form-control'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'valor_estimado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'prazo_estimado': forms.NumberInput(attrs={'class': 'form-control'}),
            'local': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        is_creating = kwargs.pop('is_creating', False)
        super().__init__(*args, **kwargs)
        
        # Filtrar obras baseado no usuário e permissões
        if user:
            from .utils import is_aprovador, is_admin, is_responsavel_empresa, is_engenheiro
            
            # Verificar se é solicitante através do grupo OU WorkOrderPermission
            is_solicitante_group = is_engenheiro(user)  # Grupo "Solicitante"
            tem_permissao_solicitante = WorkOrderPermission.objects.filter(
                usuario=user,
                tipo_permissao='solicitante',
                ativo=True
            ).exists()
            
            is_solicitante_only = (is_solicitante_group or tem_permissao_solicitante) and not (is_aprovador(user) or is_admin(user))
            
            if is_solicitante_only:
                # Solicitantes veem obras onde têm permissão (se tiverem)
                # Se não tiverem permissão específica mas estão no grupo, veem todas as obras ativas
                if tem_permissao_solicitante:
                    obras_ids = WorkOrderPermission.objects.filter(
                        usuario=user,
                        tipo_permissao='solicitante',
                        ativo=True
                    ).values_list('obra_id', flat=True)
                    self.fields['obra'].queryset = Obra.objects.filter(
                        id__in=obras_ids,
                        ativo=True
                    ).order_by('empresa', 'codigo')
                else:
                    # Está no grupo "Solicitante" mas não tem permissão específica
                    # Mostra todas as obras ativas (ou pode ser filtrado por empresa se necessário)
                    self.fields['obra'].queryset = Obra.objects.filter(ativo=True).order_by('empresa', 'codigo')
            elif is_responsavel_empresa(user) and not is_admin(user):
                # Responsáveis veem obras das empresas que gerenciam
                self.fields['obra'].queryset = Obra.objects.filter(
                    empresa__responsavel=user,
                    ativo=True
                ).order_by('empresa', 'codigo')
            else:
                # Aprovadores e admins veem todas as obras ativas
                self.fields['obra'].queryset = Obra.objects.filter(ativo=True).order_by('empresa', 'codigo')
            
            # Para solicitantes: SEMPRE esconder status, código e prazo (criação e edição)
            if is_solicitante_only:
                # Remover campos que solicitantes não devem ver
                if 'status' in self.fields:
                    del self.fields['status']
                if 'codigo' in self.fields:
                    del self.fields['codigo']
                if 'prazo_estimado' in self.fields:
                    del self.fields['prazo_estimado']
                if 'valor_estimado' in self.fields:
                    del self.fields['valor_estimado']
                if 'local' in self.fields:
                    del self.fields['local']
        else:
            self.fields['obra'].queryset = Obra.objects.filter(ativo=True).order_by('codigo')
        
        # Se estiver editando, tornar código readonly (se ainda existir)
        if self.instance.pk:
            if 'codigo' in self.fields:
                self.fields['codigo'].widget.attrs['readonly'] = True
    
    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo')
        if codigo:
            codigo = codigo.strip().upper()
            obra = self.cleaned_data.get('obra')
            
            if obra:
                # Verificar unicidade por obra
                workorder_existente = WorkOrder.objects.filter(obra=obra, codigo=codigo)
                if self.instance.pk:
                    workorder_existente = workorder_existente.exclude(pk=self.instance.pk)
                if workorder_existente.exists():
                    raise forms.ValidationError(f'Já existe um pedido com o código "{codigo}" nesta obra.')
        
        return codigo
    
    def clean_nome_credor(self):
        nome_credor = self.cleaned_data.get('nome_credor')
        if not nome_credor or not nome_credor.strip():
            raise forms.ValidationError('O nome do credor é obrigatório.')
        return nome_credor.strip()
    
    def clean_tipo_solicitacao(self):
        tipo_solicitacao = self.cleaned_data.get('tipo_solicitacao')
        if not tipo_solicitacao:
            raise forms.ValidationError('O tipo de solicitação é obrigatório.')
        return tipo_solicitacao


class AttachmentForm(forms.ModelForm):
    """
    Formulário para upload de anexos.
    """
    
    class Meta:
        model = Attachment
        fields = ['arquivo', 'nome', 'descricao']
        widgets = {
            'arquivo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.gif,.zip,.rar,.7z'
            }),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def clean_arquivo(self):
        arquivo = self.cleaned_data.get('arquivo')
        if arquivo:
            # Limite de tamanho: 50MB
            max_size = 50 * 1024 * 1024  # 50MB em bytes
            if arquivo.size > max_size:
                raise forms.ValidationError('O arquivo é muito grande. Tamanho máximo: 50MB.')
            
            # Extensões permitidas
            extensoes_permitidas = [
                '.pdf', '.doc', '.docx', '.xls', '.xlsx',
                '.jpg', '.jpeg', '.png', '.gif',
                '.zip', '.rar', '.7z'
            ]
            nome_arquivo = arquivo.name.lower()
            if not any(nome_arquivo.endswith(ext) for ext in extensoes_permitidas):
                raise forms.ValidationError(
                    f'Extensão não permitida. Extensões permitidas: {", ".join(extensoes_permitidas)}'
                )
        
        return arquivo
