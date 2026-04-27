from django import forms
from django.contrib.auth.models import Group, User
from django.forms import inlineformset_factory
from django.utils import timezone as dj_tz

from accounts.groups import GRUPOS
from gestao_aprovacao.models import Obra

from .models import (
    Comunicado,
    ComunicadoImagem,
    DestaqueVisual,
    LIM_DESC_INTERNA,
    LIM_LINK,
    LIM_SUBTITULO,
    LIM_TEXTO_BOTAO,
    LIM_TEXTO_PRINCIPAL,
    LIM_TITULO,
    LIM_TITULO_VISIVEL,
    Prioridade,
    PublicoEscopoCriterios,
    TipoConteudo,
    TipoExibicao,
)


class BaseComunicadoImagemFormSet(forms.BaseInlineFormSet):
    max_images = 5

    def clean(self):
        super().clean()
        tipo = (self.data.get('tipo_conteudo') or '').strip()
        kept = 0
        for form in self.forms:
            if self._should_delete_form(form):
                continue
            if not hasattr(form, 'cleaned_data') or form.cleaned_data is None:
                continue
            cd = form.cleaned_data
            if cd.get('arquivo'):
                kept += 1
            elif form.instance.pk and getattr(form.instance, 'arquivo', None):
                kept += 1
        if kept > self.max_images:
            raise forms.ValidationError(
                f'É permitido no máximo {self.max_images} imagens por comunicado.',
            )
        if tipo in (TipoConteudo.IMAGEM, TipoConteudo.IMAGEM_LINK):
            if kept < 1:
                raise forms.ValidationError(
                    'É obrigatório pelo menos uma imagem para os tipos Imagem e Imagem com link.',
                )


def comunicado_imagem_formset_factory():
    return inlineformset_factory(
        Comunicado,
        ComunicadoImagem,
        formset=BaseComunicadoImagemFormSet,
        fields=('arquivo',),
        extra=5,
        max_num=5,
        can_delete=True,
        widgets={'arquivo': forms.ClearableFileInput(attrs={'class': 'central-input'})},
    )


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
            'publico_escopo_criterios',
            'grupos_permitidos',
            'usuarios_permitidos',
            'obras_permitidas',
            'pode_fechar',
            'exige_confirmacao',
            'exige_resposta',
            'abrir_automaticamente',
            'mostrar_apos_fechar',
            'permitir_nao_mostrar_novamente',
        ]
        widgets = {
            'titulo': forms.TextInput(
                attrs={'class': 'central-input', 'maxlength': str(LIM_TITULO), 'autocomplete': 'off'}
            ),
            'descricao_interna': forms.Textarea(
                attrs={
                    'class': 'central-input',
                    'rows': 3,
                    'maxlength': str(LIM_DESC_INTERNA),
                }
            ),
            'titulo_visivel': forms.TextInput(
                attrs={'class': 'central-input', 'maxlength': str(LIM_TITULO_VISIVEL), 'autocomplete': 'off'}
            ),
            'subtitulo': forms.TextInput(
                attrs={'class': 'central-input', 'maxlength': str(LIM_SUBTITULO), 'autocomplete': 'off'}
            ),
            'texto_principal': forms.Textarea(
                attrs={'class': 'central-input', 'rows': 5, 'maxlength': str(LIM_TEXTO_PRINCIPAL)}
            ),
            'link_destino': forms.URLInput(
                attrs={'class': 'central-input', 'maxlength': str(LIM_LINK), 'autocomplete': 'off'}
            ),
            'texto_botao': forms.TextInput(
                attrs={'class': 'central-input', 'maxlength': str(LIM_TEXTO_BOTAO), 'autocomplete': 'off'}
            ),
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
            'grupos_permitidos': forms.CheckboxSelectMultiple(),
            'usuarios_permitidos': forms.SelectMultiple(
                attrs={'class': 'central-input select-m2m-click-toggle', 'size': '12'}
            ),
            'obras_permitidas': forms.SelectMultiple(
                attrs={'class': 'central-input select-m2m-click-toggle', 'size': '12'}
            ),
            'publico_escopo_criterios': forms.Select(
                attrs={'class': 'central-input', 'id': 'id_publico_escopo_criterios'}
            ),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_ativo'}),
            'publico_todos': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_publico_todos'}),
            'pode_fechar': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'exige_confirmacao': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'exige_resposta': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'abrir_automaticamente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'mostrar_apos_fechar': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'permitir_nao_mostrar_novamente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nomes_grupos_publico = [
            GRUPOS.ADMINISTRADOR,
            GRUPOS.APROVADOR,
            GRUPOS.SOLICITANTE,
            GRUPOS.GERENTES,
            GRUPOS.ENGENHARIA,
        ]
        self.fields['grupos_permitidos'].queryset = Group.objects.filter(
            name__in=nomes_grupos_publico
        ).order_by('name')
        uq = User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username')
        self.fields['usuarios_permitidos'].queryset = uq
        self.fields['obras_permitidas'].queryset = Obra.objects.order_by('nome', 'codigo')

        def _label_user(obj):
            return (obj.get_full_name() or obj.username or str(obj.pk)).strip()

        def _label_obra(obj):
            return f'{obj.nome} ({obj.codigo})'

        self.fields['usuarios_permitidos'].label_from_instance = _label_user
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

        self.fields['titulo'].help_text = f'Máximo de {LIM_TITULO} caracteres.'
        self.fields['titulo_visivel'].help_text = f'Máximo de {LIM_TITULO_VISIVEL} caracteres.'
        self.fields['subtitulo'].help_text = f'Máximo de {LIM_SUBTITULO} caracteres.'
        self.fields['texto_principal'].help_text = f'Máximo de {LIM_TEXTO_PRINCIPAL} caracteres.'
        self.fields['link_destino'].help_text = f'Máximo de {LIM_LINK} caracteres (URL).'
        self.fields['texto_botao'].help_text = f'Máximo de {LIM_TEXTO_BOTAO} caracteres.'

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo_conteudo')
        if tipo in (TipoConteudo.TEXTO, TipoConteudo.IMAGEM, TipoConteudo.IMAGEM_LINK):
            cleaned['pode_fechar'] = True

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

        if cleaned.get('publico_todos'):
            cleaned['publico_escopo_criterios'] = PublicoEscopoCriterios.QUALQUER
            if 'grupos_permitidos' in cleaned:
                cleaned['grupos_permitidos'] = self.fields['grupos_permitidos'].queryset.none()
            if 'usuarios_permitidos' in cleaned:
                cleaned['usuarios_permitidos'] = self.fields['usuarios_permitidos'].queryset.none()
            if 'obras_permitidas' in cleaned:
                cleaned['obras_permitidas'] = self.fields['obras_permitidas'].queryset.none()

        tipo_cf = cleaned.get('tipo_conteudo')
        if tipo_cf == TipoConteudo.FORMULARIO and cleaned.get('exige_resposta'):
            if cleaned.get('pode_fechar') or cleaned.get('permitir_nao_mostrar_novamente'):
                self.add_error(
                    'exige_resposta',
                    'Com “Resposta obrigatória” não é possível marcar “Pode fechar” nem “Permitir não mostrar novamente”. '
                    'Desmarque a resposta obrigatória ou essas opções.',
                )

        return cleaned


def reordenar_imagens_comunicado(comunicado: Comunicado) -> None:
    for i, pk in enumerate(comunicado.imagens.order_by('pk').values_list('pk', flat=True)):
        ComunicadoImagem.objects.filter(pk=pk).update(ordem=i)
