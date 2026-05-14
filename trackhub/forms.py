import json

from django import forms
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory

from mapa_obras.models import Obra

from .models import (
    ComentarioPendencia,
    EtapaPendencia,
    NotificacaoPendencia,
    Pendencia,
    PendenciaRecorrente,
)

User = get_user_model()


class PendenciaForm(forms.ModelForm):
    class Meta:
        model = Pendencia
        fields = ["obra", "titulo", "descricao", "tipo", "prioridade", "prazo"]
        widgets = {
            "prazo": forms.DateInput(attrs={"type": "date"}),
            "descricao": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, obras_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if obras_queryset is not None:
            self.fields["obra"].queryset = obras_queryset
        self.fields["obra"].widget.attrs.setdefault("class", "th-filter-select")


class EtapaForm(forms.ModelForm):
    responsavel_interno = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by("first_name"),
        required=False,
        empty_label="Selecione...",
    )

    class Meta:
        model = EtapaPendencia
        fields = [
            "titulo",
            "ordem",
            "responsavel_interno",
            "prazo",
            "observacao",
            "requer_assinatura",
        ]
        widgets = {
            "prazo": forms.DateInput(attrs={"type": "date"}),
            "observacao": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        titulo = (cleaned_data.get("titulo") or "").strip()
        if titulo:
            if not cleaned_data.get("responsavel_interno"):
                raise forms.ValidationError(
                    "Informe o responsável interno desta etapa."
                )
        return cleaned_data


EtapaFormSet = inlineformset_factory(
    Pendencia,
    EtapaPendencia,
    form=EtapaForm,
    extra=0,
    can_delete=True,
)


class ComentarioForm(forms.ModelForm):
    class Meta:
        model = ComentarioPendencia
        fields = ["texto"]
        widgets = {
            "texto": forms.Textarea(
                attrs={"rows": 2, "placeholder": "Adicionar comentário..."}
            ),
        }


class NotificacaoEtapaForm(forms.Form):
    canal = forms.ChoiceField(choices=NotificacaoPendencia.CANAL_CHOICES)
    destinatario_nome = forms.CharField(max_length=200)
    destinatario_contato = forms.CharField(max_length=200)
    mensagem = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))


class RecorrenciaPendenciaForm(forms.Form):
    """Campos extras do formulário de criação (UI customizada + JSON de parâmetros)."""

    recorrencia_regra = forms.ChoiceField(
        choices=PendenciaRecorrente.REGRA_CHOICES,
        initial=PendenciaRecorrente.REGRA_NONE,
        required=True,
        widget=forms.HiddenInput(),
    )
    recorrencia_parametros_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        initial="{}",
    )

    def clean(self):
        cleaned = super().clean()
        regra = cleaned.get("recorrencia_regra") or PendenciaRecorrente.REGRA_NONE

        raw = (cleaned.get("recorrencia_parametros_json") or "").strip() or "{}"
        try:
            pm = json.loads(raw)
        except json.JSONDecodeError:
            raise forms.ValidationError("Parâmetros de recorrência inválidos (JSON).")
        if not isinstance(pm, dict):
            pm = {}
        cleaned["recorrencia_parametros"] = pm

        if regra == PendenciaRecorrente.REGRA_NONE:
            return cleaned

        if regra == PendenciaRecorrente.REGRA_WEEKLY:
            ds = pm.get("dias_semana")
            if not isinstance(ds, list) or not ds:
                raise forms.ValidationError("Selecione pelo menos um dia da semana.")
        elif regra == PendenciaRecorrente.REGRA_MONTHLY:
            dm = pm.get("dias_mes")
            if not isinstance(dm, list) or not dm:
                raise forms.ValidationError("Selecione pelo menos um dia do mês.")
        elif regra == PendenciaRecorrente.REGRA_YEARLY:
            da = pm.get("datas_ano")
            if not isinstance(da, list) or not da:
                raise forms.ValidationError("Adicione pelo menos uma data (mês e dia).")
            for item in da:
                if not isinstance(item, dict):
                    raise forms.ValidationError("Datas anuais inválidas.")
                if "m" not in item or "d" not in item:
                    raise forms.ValidationError("Cada data anual precisa de mês e dia.")

        return cleaned


class ObraFilterForm(forms.Form):
    obra = forms.ModelChoiceField(
        queryset=Obra.objects.none(),
        required=False,
        label="Obra",
        widget=forms.Select(attrs={"class": "th-filter-select"}),
    )

    def __init__(self, *args, obras_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if obras_queryset is not None:
            self.fields["obra"].queryset = obras_queryset


_IMAGENS = {"jpg", "jpeg", "png", "gif", "webp"}
_DOCUMENTOS = {"pdf", "doc", "docx", "xls", "xlsx"}


def tipo_anexo_por_nome(filename: str) -> str | None:
    raw = (filename or "").lower().rsplit(".", 1)
    ext = raw[-1] if len(raw) >= 2 else ""
    if not ext:
        return None
    if ext in _IMAGENS:
        return "imagem"
    if ext in _DOCUMENTOS:
        return "documento"
    return "outro"


class AnexoPendenciaUploadForm(forms.Form):
    """Validação do upload AJAX (lista vinda de request.FILES.getlist)."""

    MAX_ANEXOS = 5

    def __init__(self, total_existente, files_list=None, **kwargs):
        super().__init__(**kwargs)
        self.total_existente = int(total_existente or 0)
        self.files_list = list(files_list or [])

    def clean(self):
        cleaned = super().clean()
        files = [f for f in self.files_list if f and getattr(f, "name", None)]
        if not files:
            raise forms.ValidationError("Nenhum arquivo enviado.")
        if self.total_existente + len(files) > self.MAX_ANEXOS:
            raise forms.ValidationError(
                f"Limite de {self.MAX_ANEXOS} arquivos por pendência. "
                f"Já existem {self.total_existente} arquivo(s)."
            )

        tipo_por_arquivo = []
        for f in files:
            tipo_por_arquivo.append(tipo_anexo_por_nome(f.name) or "outro")
        cleaned["validated_files"] = list(zip(files, tipo_por_arquivo))
        return cleaned
