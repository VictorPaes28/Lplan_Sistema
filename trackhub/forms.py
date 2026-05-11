from django import forms
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory

from mapa_obras.models import Obra

from .models import (
    ComentarioPendencia,
    EtapaPendencia,
    NotificacaoPendencia,
    Pendencia,
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
