from django import forms
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.utils import timezone as dj_tz

from gestao_aprovacao.models import Obra

from .models import Comunicado, DestaqueVisual, Prioridade, TipoConteudo, TipoExibicao


class ComunicadoForm(forms.ModelForm):
    class Meta:
        model = Comunicado
        fields = [
            'titulo',
            'descricao_interna',
            'ativo',
            'tipo_conteudo',
            'titulo_visivel',
            'subtitulo',
            'texto_principal',
            'imagem',
            'link_destino',
            'texto_botao',
            'destaque_visual',
            'tipo_exibicao',
            'max_exibicoes_por_usuario',
            'data_inicio',
            'data_fim',
            'dias_ativo',
            'prioridade',
            'publico_todos',
            'grupos_permitidos',
            'usuarios_permitidos',
            'obras_permitidas',
            'grupos_excluidos',
            'usuarios_excluidos',
            'pode_fechar',
            'exige_confirmacao',
            'exige_resposta',
            'bloquear_ate_acao',
            'abrir_automaticamente',
            'mostrar_apos_fechar',
            'permitir_nao_mostrar_novamente',
        ]
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'central-input'}),
            'descricao_interna': forms.Textarea(attrs={'class': 'central-input', 'rows': 3}),
            'titulo_visivel': forms.TextInput(attrs={'class': 'central-input'}),
            'subtitulo': forms.TextInput(attrs={'class': 'central-input'}),
            'texto_principal': forms.Textarea(attrs={'class': 'central-input', 'rows': 5}),
            'link_destino': forms.URLInput(attrs={'class': 'central-input'}),
            'texto_botao': forms.TextInput(attrs={'class': 'central-input'}),
            'tipo_conteudo': forms.Select(attrs={'class': 'central-input', 'id': 'id_tipo_conteudo'}),
            'tipo_exibicao': forms.Select(attrs={'class': 'central-input', 'id': 'id_tipo_exibicao'}),
            'destaque_visual': forms.Select(attrs={'class': 'central-input'}),
            'prioridade': forms.Select(attrs={'class': 'central-input'}),
            'max_exibicoes_por_usuario': forms.NumberInput(attrs={'class': 'central-input', 'min': 1}),
            'data_inicio': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'class': 'central-input', 'type': 'datetime-local'},
            ),
            'data_fim': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'class': 'central-input', 'type': 'datetime-local'},
            ),
            'dias_ativo': forms.NumberInput(attrs={'class': 'central-input', 'min': 1}),
            'imagem': forms.ClearableFileInput(attrs={'class': 'central-input'}),
            'grupos_permitidos': forms.CheckboxSelectMultiple(),
            'grupos_excluidos': forms.CheckboxSelectMultiple(),
            'usuarios_permitidos': forms.SelectMultiple(
                attrs={'class': 'central-input select-m2m-click-toggle', 'size': '12'}
            ),
            'usuarios_excluidos': forms.SelectMultiple(
                attrs={'class': 'central-input select-m2m-click-toggle', 'size': '12'}
            ),
            'obras_permitidas': forms.SelectMultiple(
                attrs={'class': 'central-input select-m2m-click-toggle', 'size': '12'}
            ),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_ativo'}),
            'publico_todos': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_publico_todos'}),
            'pode_fechar': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'exige_confirmacao': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'exige_resposta': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'bloquear_ate_acao': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'abrir_automaticamente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'mostrar_apos_fechar': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'permitir_nao_mostrar_novamente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['grupos_permitidos'].queryset = Group.objects.order_by('name')
        self.fields['grupos_excluidos'].queryset = Group.objects.order_by('name')
        uq = User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username')
        self.fields['usuarios_permitidos'].queryset = uq
        self.fields['usuarios_excluidos'].queryset = uq
        self.fields['obras_permitidas'].queryset = Obra.objects.order_by('nome', 'codigo')

        def _label_user(obj):
            return (obj.get_full_name() or obj.username or str(obj.pk)).strip()

        def _label_obra(obj):
            return f'{obj.nome} ({obj.codigo})'

        self.fields['usuarios_permitidos'].label_from_instance = _label_user
        self.fields['usuarios_excluidos'].label_from_instance = _label_user
        self.fields['obras_permitidas'].label_from_instance = _label_obra
        self.fields['tipo_conteudo'].choices = TipoConteudo.choices
        self.fields['tipo_exibicao'].choices = TipoExibicao.choices
        self.fields['destaque_visual'].choices = DestaqueVisual.choices
        self.fields['prioridade'].choices = Prioridade.choices

        for name in ('data_inicio', 'data_fim'):
            val = getattr(self.instance, name, None)
            if val and self.instance.pk:
                local = dj_tz.localtime(val) if dj_tz.is_aware(val) else val
                self.initial[name] = local.strftime('%Y-%m-%dT%H:%M')

        fmts = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S']
        self.fields['data_inicio'].input_formats = fmts
        self.fields['data_fim'].input_formats = fmts

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo_conteudo')
        imagem = cleaned.get('imagem')
        has_imagem = bool(imagem) or (self.instance.pk and self.instance.imagem)
        if tipo in (TipoConteudo.IMAGEM, TipoConteudo.IMAGEM_LINK):
            if not has_imagem:
                self.add_error('imagem', 'É obrigatório enviar uma imagem para este tipo de conteúdo.')

        tipo_ex = cleaned.get('tipo_exibicao')
        if tipo_ex == TipoExibicao.X_VEZES:
            max_v = cleaned.get('max_exibicoes_por_usuario')
            if max_v is None or max_v < 1:
                self.add_error(
                    'max_exibicoes_por_usuario',
                    'Informe o número máximo de exibições por usuário (≥ 1).',
                )

        if tipo_ex == TipoExibicao.X_DIAS:
            dias = cleaned.get('dias_ativo')
            if dias is None or dias < 1:
                self.add_error('dias_ativo', 'Informe a quantidade de dias (≥ 1) para este tipo de exibição.')

        di = cleaned.get('data_inicio')
        df = cleaned.get('data_fim')
        if di and df and df < di:
            self.add_error('data_fim', 'A data de fim deve ser posterior à data de início.')

        # Com "Público: todos" marcado, grupos/usuários/obras permitidos não devem contar.
        # Senão o HTML pode ainda enviar checkboxes marcados (secção oculta) e o backend grava
        # publico_todos=True com M2M preenchido — em services o 1.º if (publico_todos) libera todos.
        if cleaned.get('publico_todos'):
            if 'grupos_permitidos' in cleaned:
                cleaned['grupos_permitidos'] = self.fields['grupos_permitidos'].queryset.none()
            if 'usuarios_permitidos' in cleaned:
                cleaned['usuarios_permitidos'] = self.fields['usuarios_permitidos'].queryset.none()
            if 'obras_permitidas' in cleaned:
                cleaned['obras_permitidas'] = self.fields['obras_permitidas'].queryset.none()

        return cleaned
