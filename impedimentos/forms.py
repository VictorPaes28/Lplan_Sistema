import re

from django import forms
from django.contrib.auth import get_user_model

from core.models import ProjectMember

from .models import CategoriaImpedimento, Impedimento, StatusImpedimento


User = get_user_model()


class ImpedimentoForm(forms.ModelForm):
    class Meta:
        model = Impedimento
        fields = [
            "titulo",
            "descricao",
            "prioridade",
            "responsaveis",
            "prazo",
            "categorias",
        ]
        widgets = {
            "titulo": forms.TextInput(
                attrs={
                    "placeholder": "Ex.: Aguardando liberação de acesso ao canteiro",
                    "class": "imp-modal-titulo-input",
                }
            ),
            "descricao": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Descreva detalhes da restrição"}
            ),
            "prazo": forms.DateInput(
                attrs={"type": "date", "class": "imp-input-date"}
            ),
            "responsaveis": forms.SelectMultiple(
                attrs={
                    "class": "imp-responsaveis-select",
                    "aria-hidden": "true",
                    "tabindex": "-1",
                }
            ),
            "categorias": forms.SelectMultiple(
                attrs={
                    "class": "imp-categorias-select",
                    "aria-hidden": "true",
                    "tabindex": "-1",
                }
            ),
        }

    def __init__(self, *args, obra=None, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.obra = obra
        self.project = project
        self.fields["titulo"].required = True

        if project is not None:
            member_ids = ProjectMember.objects.filter(
                project=project, user__is_active=True
            ).values_list("user_id", flat=True)
            self.fields["responsaveis"].queryset = User.objects.filter(
                pk__in=member_ids, is_active=True
            ).order_by("first_name", "last_name", "username")
        else:
            self.fields["responsaveis"].queryset = User.objects.none()

        if obra is not None:
            self.fields["categorias"].queryset = CategoriaImpedimento.objects.filter(
                obra=obra
            ).order_by("nome")
        else:
            self.fields["categorias"].queryset = CategoriaImpedimento.objects.none()
        self.fields["categorias"].required = True

    def clean_categorias(self):
        cats = self.cleaned_data.get("categorias")
        if not cats or not cats.exists():
            raise forms.ValidationError("Selecione pelo menos uma categoria.")
        return cats

    def clean_titulo(self):
        titulo = (self.cleaned_data.get("titulo") or "").strip()
        if not titulo:
            raise forms.ValidationError("Informe um título para a restrição.")
        return titulo


class CategoriaImpedimentoForm(forms.ModelForm):
    class Meta:
        model = CategoriaImpedimento
        fields = ["nome", "cor"]
        widgets = {
            "nome": forms.TextInput(attrs={"maxlength": "100", "class": "imp-cat-form-nome"}),
            "cor": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "imp-cat-form-cor",
                    "title": "Cor da categoria",
                }
            ),
        }

    def __init__(self, *args, obra=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.obra = obra
        self.fields["nome"].required = True
        self.fields["cor"].required = False

    def clean_nome(self):
        nome = (self.cleaned_data.get("nome") or "").strip()
        if not nome:
            raise forms.ValidationError("Informe o nome da categoria.")
        if self.obra is None:
            return nome
        qs = CategoriaImpedimento.objects.filter(obra=self.obra, nome__iexact=nome)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe uma categoria com este nome nesta obra.")
        return nome

    def clean_cor(self):
        cor = (self.cleaned_data.get("cor") or "").strip() or "#6B7280"
        if not re.match(r"^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$", cor):
            raise forms.ValidationError("Use hexadecimal válido, ex: #3B82F6 ou #3CF.")
        if len(cor) == 4:
            cor = "#" + "".join(ch * 2 for ch in cor[1:])
        return cor.upper()


class StatusImpedimentoForm(forms.ModelForm):
    class Meta:
        model = StatusImpedimento
        fields = ["nome", "cor", "ordem", "is_default"]
        labels = {
            "is_default": "Padrão para novas restrições",
        }
        widgets = {
            "nome": forms.TextInput(attrs={"maxlength": "100"}),
            "cor": forms.TextInput(
                attrs={
                    "type": "color",
                    "title": "Cor do status",
                    "class": "imp-status-color-input",
                }
            ),
            "ordem": forms.NumberInput(attrs={"min": "1", "step": "1"}),
            "is_default": forms.CheckboxInput(attrs={"class": "imp-checkbox"}),
        }

    def __init__(self, *args, obra=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.obra = obra
        self.fields["nome"].required = True
        self.fields["cor"].required = True
        self.fields["ordem"].required = True

    def clean_ordem(self):
        ordem = self.cleaned_data.get("ordem")
        if ordem is None:
            raise forms.ValidationError("Informe a ordem de exibição.")
        if ordem < 1:
            raise forms.ValidationError("A ordem deve ser pelo menos 1.")
        return ordem

    def clean_cor(self):
        cor = (self.cleaned_data.get("cor") or "").strip()
        if not cor:
            raise forms.ValidationError("Informe uma cor.")
        if not re.match(r"^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$", cor):
            raise forms.ValidationError("Use hexadecimal válido, ex: #3B82F6 ou #3CF.")
        if len(cor) == 4:
            cor = "#" + "".join(ch * 2 for ch in cor[1:])
        return cor.upper()

    def clean_nome(self):
        nome = (self.cleaned_data.get("nome") or "").strip()
        if not nome:
            raise forms.ValidationError("Informe o nome do status.")
        if self.obra is None:
            return nome
        qs = StatusImpedimento.objects.filter(obra=self.obra, nome__iexact=nome)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe um status com este nome nesta obra.")
        return nome

    def clean(self):
        cleaned = super().clean()
        if self.obra is None:
            return cleaned
        is_def = cleaned.get("is_default")
        if self.instance and self.instance.pk:
            was_default = (
                StatusImpedimento.objects.filter(pk=self.instance.pk)
                .values_list("is_default", flat=True)
                .first()
            )
            if was_default and not is_def:
                has_other = (
                    StatusImpedimento.objects.filter(obra=self.obra, is_default=True)
                    .exclude(pk=self.instance.pk)
                    .exists()
                )
                if not has_other:
                    raise forms.ValidationError(
                        "Marque outro status como padrão antes de remover o padrão deste."
                    )
        return cleaned
