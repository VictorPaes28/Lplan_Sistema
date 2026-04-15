"""
Formulários para gestão de LocalObra (Mapa de Suprimentos) a partir do projeto canónico.
"""
from __future__ import annotations

from django import forms

from mapa_obras.models import LocalObra, Obra


def coletar_ids_descendentes(local_id: int) -> set[int]:
    """IDs do próprio nó e de todos os descendentes (filhos recursivos)."""
    out: set[int] = set()
    stack = [local_id]
    while stack:
        pk = stack.pop()
        if pk in out:
            continue
        out.add(pk)
        stack.extend(
            LocalObra.objects.filter(parent_id=pk).values_list('id', flat=True)
        )
    return out


class LocalObraPainelForm(forms.ModelForm):
    """Criar ou editar local dentro de uma obra fixa."""

    class Meta:
        model = LocalObra
        fields = ('nome', 'tipo', 'parent')
        labels = {
            'nome': 'Nome do local',
            'tipo': 'Tipo',
            'parent': 'Faz parte de outro local?',
        }
        widgets = {
            'nome': forms.TextInput(
                attrs={
                    'class': 'locais-input',
                    'maxlength': 100,
                    'placeholder': 'Ex.: Bloco A, Apartamento 101, Lobby…',
                    'autocomplete': 'off',
                }
            ),
            'tipo': forms.Select(attrs={'class': 'locais-select'}),
            'parent': forms.Select(attrs={'class': 'locais-select'}),
        }

    def __init__(
        self,
        *args,
        obra: Obra,
        excluir_parent_ids: frozenset[int] | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._obra = obra
        qs = LocalObra.objects.filter(obra=obra).order_by('tipo', 'nome')
        if excluir_parent_ids:
            qs = qs.exclude(pk__in=excluir_parent_ids)
        self.fields['parent'].queryset = qs
        self.fields['parent'].required = False
        self.fields['parent'].empty_label = 'Não — é só este local na obra'
        self.fields['parent'].help_text = (
            'Na maioria dos casos deixe esta primeira opção. Só escolha outro local na lista se '
            'este nome for uma subdivisão dele (ex.: «Apartamento 12» dentro do «Bloco B» já cadastrado).'
        )

    def clean_nome(self):
        nome = (self.cleaned_data.get('nome') or '').strip()
        if not nome:
            raise forms.ValidationError('Indique o nome do local.')
        if len(nome) > 100:
            raise forms.ValidationError('Nome demasiado longo (máx. 100 caracteres).')
        return nome

    def clean(self):
        cleaned = super().clean()
        parent = cleaned.get('parent')
        nome = (cleaned.get('nome') or '').strip()
        if parent and parent.obra_id != self._obra.pk:
            self.add_error('parent', 'O local escolhido tem de pertencer à mesma obra.')
        if nome and parent is not None:
            qs = LocalObra.objects.filter(
                obra=self._obra,
                nome=nome,
                parent=parent,
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    'nome',
                    'Já existe um local com este nome neste agrupamento. '
                    'Altere o nome ou indique outro local em «Faz parte de outro local?».',
                )
        return cleaned

    def save(self, commit=True):
        self.instance.obra = self._obra
        return super().save(commit=commit)
