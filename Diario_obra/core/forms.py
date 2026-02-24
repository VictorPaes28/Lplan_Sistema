"""
Forms Django para Diário de Obra V2.0 - LPLAN
"""
from decimal import Decimal
from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import (
    ConstructionDiary,
    DiaryImage,
    DailyWorkLog,
    Labor,
    Equipment,
    Project,
    Activity,
    DiaryOccurrence,
    OccurrenceTag,
    ActivityStatus,
)

User = get_user_model()


class ConstructionDiaryForm(forms.ModelForm):
    """Form para ConstructionDiary."""
    
    date = forms.DateField(
        input_formats=['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'],
        widget=forms.DateInput(attrs={
            'type': 'date',
            'id': 'id_date',
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-600 focus:border-blue-600 outline-none text-sm',
        }, format='%Y-%m-%d'),
    )
    
    weather_morning = forms.ChoiceField(
        choices=[
            ('sol', 'Sol'),
            ('nublado', 'Nublado'),
            ('chuva', 'Chuva'),
        ],
        required=False,
        widget=forms.HiddenInput()
    )
    
    weather_afternoon = forms.ChoiceField(
        choices=[
            ('sol', 'Sol'),
            ('nublado', 'Nublado'),
            ('chuva', 'Chuva'),
        ],
        required=False,
        widget=forms.HiddenInput()
    )
    
    class Meta:
        model = ConstructionDiary
        fields = [
            'project',
            'date',
            'weather_conditions',
            'weather_morning_condition',
            'weather_morning_workable',
            'weather_afternoon_condition',
            'weather_afternoon_workable',
            'weather_night_enabled',
            'weather_night_type',
            'weather_night_workable',
            'pluviometric_index',
            'rain_occurrence',
            'rain_observations',
            'deliberations',
            'work_hours',
            'accidents',
            'stoppages',
            'imminent_risks',
            'incidents',
            'inspections',
            'dds',
            'general_notes',
            'inspection_responsible',
            'production_responsible',
        ]
        widgets = {
            'project': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
            }),
            'weather_conditions': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'placeholder': 'Descreva as condições climáticas do dia...',
            }),
            'rain_occurrence': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
            }, choices=[
                ('', 'Nenhuma'),
                ('F', 'Fraca'),
                ('M', 'Média'),
                ('S', 'Forte'),
            ]),
            'rain_observations': forms.Textarea(attrs={
                'rows': 2,
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'placeholder': 'Observações sobre ocorrência de chuvas...',
            }),
            'deliberations': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'placeholder': 'Deliberações e decisões tomadas no dia...',
            }),
            'work_hours': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'placeholder': 'Ex: 8.00',
                'step': '0.25',
                'min': '0',
                'max': '99.99',  # Permite turnos longos e horas extras (max_digits=4 no modelo)
            }),
            'inspection_responsible': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'placeholder': 'Nome do responsável pela inspeção diária...',
            }),
            'production_responsible': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'placeholder': 'Nome do responsável pela produção...',
            }),
            'weather_morning_condition': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
            }, choices=[
                ('', 'Não informado'),
                ('B', 'Bom'),
                ('R', 'Ruim'),
            ]),
            'weather_morning_workable': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
            }, choices=[
                ('', 'Não informado'),
                ('T', 'Trabalhável'),
                ('N', 'Não Trabalhável'),
            ]),
            'weather_afternoon_condition': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
            }, choices=[
                ('', 'Não informado'),
                ('B', 'Bom'),
                ('R', 'Ruim'),
            ]),
            'weather_afternoon_workable': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
            }, choices=[
                ('', 'Não informado'),
                ('T', 'Trabalhável'),
                ('N', 'Não Trabalhável'),
            ]),
            'weather_night_enabled': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500',
            }),
            'weather_night_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
            }, choices=[
                ('', 'Não informado'),
                ('C', 'Claro'),
                ('N', 'Nublado'),
                ('CH', 'Chuvoso'),
            ]),
            'weather_night_workable': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
            }, choices=[
                ('', 'Não informado'),
                ('P', 'Praticável'),
                ('I', 'Impraticável'),
            ]),
            'pluviometric_index': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 pr-12 border border-slate-300 rounded-lg focus:ring-2 focus:ring-slate-500 focus:border-slate-500 outline-none transition-all text-sm text-slate-900 placeholder:text-slate-400',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
            }),
            'accidents': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-2 border border-red-200 rounded-lg focus:ring-2 focus:ring-red-600 focus:border-transparent outline-none',
                'placeholder': 'Registre acidentes ocorridos no dia...',
            }),
            'stoppages': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-2 border border-orange-200 rounded-lg focus:ring-2 focus:ring-orange-600 focus:border-transparent outline-none',
                'placeholder': 'Registre paralisações, interrupções ou paradas no trabalho...',
            }),
            'imminent_risks': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-2 border border-yellow-200 rounded-lg focus:ring-2 focus:ring-yellow-600 focus:border-transparent outline-none',
                'placeholder': 'Registre riscos eminentes identificados no dia...',
            }),
            'incidents': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'placeholder': 'Registre outros incidentes ou eventos relevantes...',
            }),
            'inspections': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-2 border border-blue-200 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'placeholder': 'Registre fiscalizações realizadas no dia...',
            }),
            'dds': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-2 border border-green-200 rounded-lg focus:ring-2 focus:ring-green-600 focus:border-transparent outline-none',
                'placeholder': 'Registre o Discurso Diário de Segurança realizado...',
            }),
            'general_notes': forms.Textarea(attrs={
                'rows': 5,
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'placeholder': 'Observações gerais sobre o dia de trabalho...',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)
        
        # Armazena o projeto para uso posterior
        self._project = project
        
        # Se projeto foi passado, usa ele e oculta o campo
        if project:
            self.fields['project'].initial = project
            self.fields['project'].widget = forms.HiddenInput()
            # Garante que o projeto seja definido na instância se for um novo diário
            if self.instance and not self.instance.pk:
                # Se for uma nova instância, define o projeto antes da validação
                self.instance.project = project
            # Também garante que o campo tenha o valor correto
            if 'project' not in self.data:
                # Se o campo não estiver no POST, força o valor
                self.data = self.data.copy() if hasattr(self.data, 'copy') else self.data
                if hasattr(self.data, '_mutable'):
                    self.data._mutable = True
                if isinstance(self.data, dict):
                    self.data['project'] = project.pk
                elif hasattr(self.data, '__setitem__'):
                    self.data['project'] = str(project.pk)
        else:
            # Filtra projetos ativos
            self.fields['project'].queryset = Project.objects.filter(is_active=True)
        
        # Se for edição, verifica permissões
        if self.instance and self.instance.pk:
            if not self.instance.can_be_edited_by(user):
                for field in self.fields:
                    self.fields[field].widget.attrs['readonly'] = True
                    self.fields[field].widget.attrs['disabled'] = True
    
    def clean_date(self):
        """Valida que a data não seja futura e esteja dentro do período do projeto."""
        from datetime import date
        
        date_value = self.cleaned_data.get('date')
        if date_value:
            today = date.today()
            # Não permite data futura
            if date_value > today:
                raise forms.ValidationError(
                    "Não é possível criar um diário para uma data futura."
                )
            
            # Validar que a data está dentro do período do projeto
            project = getattr(self, '_project', None) or self.cleaned_data.get('project')
            if project:
                if project.start_date and date_value < project.start_date:
                    raise forms.ValidationError(
                        f"A data do diário ({date_value.strftime('%d/%m/%Y')}) é anterior ao "
                        f"início do projeto ({project.start_date.strftime('%d/%m/%Y')})."
                    )
                if project.end_date and date_value > project.end_date:
                    raise forms.ValidationError(
                        f"A data do diário ({date_value.strftime('%d/%m/%Y')}) é posterior ao "
                        f"término do projeto ({project.end_date.strftime('%d/%m/%Y')})."
                    )
        return date_value
    
    def clean(self):
        cleaned_data = super().clean()
        # Sempre usar o projeto passado pelo servidor (__init__), nunca confiar no POST (evita adulteração)
        if getattr(self, '_project', None):
            project = self._project
            cleaned_data['project'] = project
        else:
            project = cleaned_data.get('project')
        date = cleaned_data.get('date')
        
        # Garante instância com projeto correto (novo diário ou instância sem projeto)
        if project and self.instance and (not self.instance.pk or not getattr(self.instance.project, 'pk', None)):
            self.instance.project = project
        
        # Valida unicidade projeto + data (antes da validação do modelo)
        # Isso permite uma mensagem de erro mais amigável
        if project and date:
            existing = ConstructionDiary.objects.filter(
                project=project,
                date=date
            )
            # Se estiver editando, exclui o próprio registro
            # Verifica tanto self.instance.pk quanto self.instance.id para garantir
            instance_pk = None
            if self.instance:
                instance_pk = getattr(self.instance, 'pk', None) or getattr(self.instance, 'id', None)
            
            if instance_pk:
                existing = existing.exclude(pk=instance_pk)
            
            if existing.exists():
                existing_diary = existing.first()
                # Se estiver editando o mesmo diário (mesma data), não deve dar erro
                if instance_pk and existing_diary.pk == instance_pk:
                    # Não deve chegar aqui, mas por segurança
                    pass
                else:
                    raise forms.ValidationError({
                        '__all__': [
                            f"Já existe um relatório para esta obra na data {date.strftime('%d/%m/%Y')}. "
                            f"Por favor, escolha outra data ou edite o relatório existente."
                        ]
                    })
        
        # Combina clima manhã e tarde
        weather_morning = cleaned_data.get('weather_morning', '')
        weather_afternoon = cleaned_data.get('weather_afternoon', '')
        
        if weather_morning or weather_afternoon:
            weather_parts = []
            if weather_morning:
                weather_parts.append(f"Manhã: {dict(self.fields['weather_morning'].choices).get(weather_morning, weather_morning)}")
            if weather_afternoon:
                weather_parts.append(f"Tarde: {dict(self.fields['weather_afternoon'].choices).get(weather_afternoon, weather_afternoon)}")
            
            if weather_parts:
                cleaned_data['weather_conditions'] = ' | '.join(weather_parts)
        
        return cleaned_data


class DiaryImageForm(forms.ModelForm):
    """Form para DiaryImage."""
    
    class Meta:
        model = DiaryImage
        fields = ['image', 'caption', 'is_approved_for_report']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100',
                'accept': 'image/*',
            }),
            'caption': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'placeholder': 'Legenda da foto (obrigatório, ex: "Bloco C, serviço tal")...',
            }),
            'is_approved_for_report': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Caption é obrigatório quando há imagem (validado no clean())
        # Em formsets, required=True no caption faria todos os forms vazios falharem; mantemos validação no clean()
        self.fields['caption'].required = False
        self.fields['caption'].widget.attrs.pop('required', None)
        
        # Remove IDs dos campos para evitar duplicação em formsets
        # Adiciona aria-labels para acessibilidade
        if 'image' in self.fields:
            self.fields['image'].widget.attrs.pop('id', None)
            self.fields['image'].widget.attrs['aria-label'] = 'Upload de imagem'
        if 'caption' in self.fields:
            self.fields['caption'].widget.attrs.pop('id', None)
            self.fields['caption'].widget.attrs['aria-label'] = 'Legenda da foto'
        if 'is_approved_for_report' in self.fields:
            self.fields['is_approved_for_report'].widget.attrs.pop('id', None)
            self.fields['is_approved_for_report'].widget.attrs['aria-label'] = 'Foto aprovada para relatório'
    
    def full_clean(self):
        """Sobrescreve full_clean para ignorar validação de formulários vazios."""
        # Verifica ANTES da validação se o formulário está vazio
        if hasattr(self, 'data') and self.data:
            prefix = self.prefix if hasattr(self, 'prefix') and self.prefix else ''
            if prefix:
                image_key = f'{prefix}-image'
                caption_key = f'{prefix}-caption'
            else:
                image_key = 'image'
                caption_key = 'caption'
            
            # Verifica se há arquivo sendo enviado
            has_image = False
            if hasattr(self, 'files') and self.files:
                # Tenta encontrar o arquivo pelo nome exato
                has_image = image_key in self.files and self.files.get(image_key) is not None
                # Se não encontrou, tenta buscar por qualquer chave que contenha o nome do campo
                if not has_image:
                    for key in self.files.keys():
                        if image_key in key or key.endswith('-image'):
                            has_image = True
                            # Atualiza o image_key para o nome correto encontrado
                            image_key = key
                            break
            
            # Verifica se há legenda (trata strings vazias como None)
            caption_raw = self.data.get(caption_key, '') if caption_key in self.data else ''
            has_caption = caption_raw and isinstance(caption_raw, str) and caption_raw.strip()
            
            has_pk = self.instance.pk if hasattr(self, 'instance') and self.instance else False
            
            # Se está completamente vazio, pula a validação
            if not has_image and not has_caption and not has_pk:
                self._errors = {}
                self.cleaned_data = {}
                return
        
        # Chama a validação padrão
        super().full_clean()
    
    def clean(self):
        """Validação customizada para o form de imagem."""
        from .utils.file_validators import validate_image_file
        
        cleaned_data = super().clean()
        image = cleaned_data.get('image')
        # Trata strings vazias como None (sem legenda)
        caption_raw = cleaned_data.get('caption')
        caption = caption_raw.strip() if caption_raw and isinstance(caption_raw, str) and caption_raw.strip() else None
        has_pk = self.instance.pk if hasattr(self, 'instance') and self.instance else False
        
        # Se o formulário está completamente vazio (sem imagem, sem legenda, sem pk), não valida
        # Isso permite que formulários vazios do formset sejam ignorados
        if not image and not caption and not has_pk:
            # Remove todos os erros para este formulário vazio
            self._errors = {}
            # Limpa o campo caption se estiver vazio
            if 'caption' in cleaned_data and not caption:
                cleaned_data['caption'] = None
            # Retorna dados vazios mas válidos
            return cleaned_data
        
        # Valida arquivo de imagem (tamanho, tipo MIME, extensão, sanitização)
        if image:
            try:
                validate_image_file(image)
            except ValidationError as e:
                raise ValidationError({'image': str(e)})
        
        # Se há uma imagem, a legenda é obrigatória
        if image and not caption:
            raise ValidationError({
                'caption': 'A legenda é obrigatória quando uma foto é adicionada.'
            })
        
        # Se há legenda mas não há imagem e não é uma edição (sem pk), isso é um erro
        if caption and not image and not has_pk:
            raise ValidationError({
                'image': 'É necessário selecionar uma foto quando uma legenda é fornecida.'
            })
        
        return cleaned_data


class DailyWorkLogForm(forms.ModelForm):
    """Form para DailyWorkLog."""
    
    class Meta:
        model = DailyWorkLog
        fields = [
            'location',
            'work_stage',
            'percentage_executed_today',
            'accumulated_progress_snapshot',
            'notes',
        ]
        widgets = {
            'work_stage': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-slate-500 focus:border-slate-500 outline-none text-sm text-slate-900',
            }),
            'location': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-slate-500 focus:border-slate-500 outline-none text-sm text-slate-900 placeholder:text-slate-400 transition-all',
                'placeholder': 'Local da atividade (ex: Bloco A, Andar 2, Sala 101)...',
            }),
            'percentage_executed_today': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-slate-500 focus:border-slate-500 outline-none text-sm text-slate-900 transition-all',
                'step': '0.01',
                'min': '0',
                'max': '200',  # Permite até 200% para casos especiais (ex: trabalho extra)
            }),
            'accumulated_progress_snapshot': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-slate-500 focus:border-slate-500 outline-none text-sm text-slate-900 transition-all',
                'step': '0.01',
                'min': '0',
                'max': '200',  # Permite até 200% para casos especiais
            }),
            'notes': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-slate-500 focus:border-slate-500 outline-none text-sm text-slate-900 placeholder:text-slate-400 transition-all resize-y',
                'placeholder': 'Notas sobre o trabalho realizado...',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        diary = kwargs.pop('diary', None)
        super().__init__(*args, **kwargs)
        
        # Remove o campo activity do formulário e adiciona um campo de texto livre
        if 'activity' in self.fields:
            # Remove o campo ForeignKey
            del self.fields['activity']
        
        # Torna accumulated_progress_snapshot opcional (não obrigatório)
        if 'accumulated_progress_snapshot' in self.fields:
            self.fields['accumulated_progress_snapshot'].required = False
        
        # Torna percentage_executed_today opcional também
        if 'percentage_executed_today' in self.fields:
            self.fields['percentage_executed_today'].required = False
        
        # Adiciona campo de texto livre para atividade (textarea)
        self.fields['activity_description'] = forms.CharField(
            required=True,
            max_length=1000,
            widget=forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-slate-500 focus:border-slate-500 outline-none text-sm text-slate-900 placeholder:text-slate-400 transition-all resize-y max-h-24',
                'placeholder': 'Descreva a atividade executada...',
                'rows': 2,
            }),
            label='Descrição',
            help_text='Descreva a atividade executada'
        )
        
        # Adiciona campos opcionais
        self.fields['quantity_done'] = forms.DecimalField(
            required=False,
            widget=forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-slate-500 focus:border-slate-500 outline-none text-sm text-slate-900 placeholder:text-slate-400 transition-all',
                'placeholder': 'Ex.: 90.5',
                'step': '0.01',
            }),
            label='Qtd. Realizada',
        )
        
        self.fields['unit'] = forms.CharField(
            required=False,
            max_length=20,
            widget=forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-slate-500 focus:border-slate-500 outline-none text-sm text-slate-900 placeholder:text-slate-400 transition-all',
                'placeholder': 'Ex.: m²',
            }),
            label='Unidade',
        )
        
        # work_stage (Status: Início, Andamento, Término) já está em Meta.fields
        if 'work_stage' in self.fields:
            self.fields['work_stage'].required = False
            self.fields['work_stage'].label = 'Status'
        
        self.fields['start_time'] = forms.TimeField(
            required=False,
            widget=forms.TimeInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-slate-500 focus:border-slate-500 outline-none text-sm text-slate-900 placeholder:text-slate-400 transition-all',
                'placeholder': 'hh:mm',
                'type': 'time',
            }),
            label='Hora início',
        )
        
        self.fields['end_time'] = forms.TimeField(
            required=False,
            widget=forms.TimeInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-slate-500 focus:border-slate-500 outline-none text-sm text-slate-900 placeholder:text-slate-400 transition-all',
                'placeholder': 'hh:mm',
                'type': 'time',
            }),
            label='Hora fim',
        )
        
        # Se for edição e tiver activity, preenche o campo de texto
        if self.instance and self.instance.pk and self.instance.activity:
            self.fields['activity_description'].initial = self.instance.activity.name
        
        # Armazena diary para usar no save
        self.diary = diary
    
    def clean(self):
        """Validações customizadas para DailyWorkLog."""
        cleaned_data = super().clean()
        activity_description = cleaned_data.get('activity_description', '').strip()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        # REMOVE qualquer campo status que possa ter vindo do POST (não existe no modelo)
        if 'status' in cleaned_data:
            del cleaned_data['status']
        
        percentage_executed = cleaned_data.get('percentage_executed_today')
        accumulated_progress = cleaned_data.get('accumulated_progress_snapshot')
        
        # Valida que activity_description não esteja vazio
        if not activity_description:
            raise ValidationError({
                'activity_description': 'A descrição da atividade é obrigatória.'
            })
        
        # Valida que hora fim seja posterior à hora início
        if start_time and end_time:
            if end_time <= start_time:
                raise ValidationError({
                    'end_time': 'A hora de término deve ser posterior à hora de início.'
                })
        
        # Define valores padrão se não fornecidos (campos opcionais)
        if percentage_executed is None:
            cleaned_data['percentage_executed_today'] = Decimal('0.00')
            percentage_executed = Decimal('0.00')
        
        if accumulated_progress is None:
            cleaned_data['accumulated_progress_snapshot'] = Decimal('0.00')
            accumulated_progress = Decimal('0.00')
        
        # Valida porcentagens (permite até 200% para casos especiais, mas avisa se > 100%)
        if percentage_executed is not None:
            if percentage_executed < 0:
                raise ValidationError({
                    'percentage_executed_today': 'A porcentagem executada não pode ser negativa.'
                })
            if percentage_executed > 200:
                raise ValidationError({
                    'percentage_executed_today': 'A porcentagem executada não pode ser superior a 200%.'
                })
        
        if accumulated_progress is not None:
            if accumulated_progress < 0:
                raise ValidationError({
                    'accumulated_progress_snapshot': 'O progresso acumulado não pode ser negativa.'
                })
            if accumulated_progress > 200:
                raise ValidationError({
                    'accumulated_progress_snapshot': 'O progresso acumulado não pode ser superior a 200%.'
                })
        
        return cleaned_data
    
    def save(self, commit=True):
        """Salva o form criando uma Activity automaticamente se necessário."""
        from core.models import Activity
        from django.db import transaction, IntegrityError
        import logging
        import time
        
        logger = logging.getLogger(__name__)
        instance = super().save(commit=False)
        
        # Pega o texto da atividade
        activity_description = self.cleaned_data.get('activity_description', '').strip()
        
        if not activity_description:
            raise ValidationError({
                'activity_description': 'A descrição da atividade é obrigatória.'
            })
        
        if not self.diary or not self.diary.project:
            raise ValidationError('Diário e projeto são obrigatórios para criar worklog.')
        
        if activity_description and self.diary and self.diary.project:
            # Busca uma Activity existente com este nome no projeto
            try:
                activity = Activity.objects.get(
                    project=self.diary.project,
                    name=activity_description
                )
                instance.activity = activity
                logger.info(f"Activity encontrada por nome: {activity.code}")
            except Activity.DoesNotExist:
                # Se não existe, cria uma nova Activity como raiz
                # Treebeard requer usar add_root() para criar nós raiz
                try:
                    with transaction.atomic():
                        # Gera código base
                        base_code = f'GEN-{activity_description[:20].upper().replace(" ", "-").replace("/", "-")}'
                        code = base_code
                        
                        # Tenta criar como raiz
                        # Se já existe uma raiz com este código, tenta com sufixo
                        max_attempts = 5
                        for attempt in range(max_attempts):
                            try:
                                # Verifica se já existe uma raiz com este código
                                existing = Activity.objects.filter(
                                    project=self.diary.project,
                                    code=code
                                ).first()
                                
                                if existing:
                                    if attempt < max_attempts - 1:
                                        code = f'{base_code}-{int(time.time()) % 10000}'
                                        logger.warning(f"Código {base_code} já existe, tentando {code}")
                                        continue
                                    else:
                                        # Usa a existente
                                        activity = existing
                                        break
                                
                                # Cria nova Activity como raiz
                                activity = Activity.add_root(
                                    project=self.diary.project,
                                    name=activity_description,
                                    code=code,
                                    description=f'Atividade criada automaticamente: {activity_description}',
                                    weight=Decimal('0.00'),
                                    status=ActivityStatus.NOT_STARTED
                                )
                                logger.info(f"Activity criada como raiz: {activity.code}")
                                break
                            except IntegrityError as e:
                                if attempt < max_attempts - 1:
                                    code = f'{base_code}-{int(time.time()) % 10000}'
                                    logger.warning(f"Erro ao criar Activity: {e}, tentando {code}")
                                else:
                                    # Última tentativa: busca por nome novamente
                                    try:
                                        activity = Activity.objects.get(
                                            project=self.diary.project,
                                            name=activity_description
                                        )
                                        logger.info(f"Activity encontrada após tentativas: {activity.code}")
                                        break
                                    except Activity.DoesNotExist:
                                        logger.error(f"Não foi possível criar ou encontrar Activity para: {activity_description}")
                                        raise ValidationError({
                                            'activity_description': f'Erro ao criar atividade. Tente novamente.'
                                        })
                        
                        instance.activity = activity
                except Exception as e:
                    logger.error(f"Erro ao criar Activity: {e}", exc_info=True)
                    raise ValidationError({
                        'activity_description': f'Erro ao criar atividade: {str(e)}'
                    })
        
        if commit:
            # Verifica se activity e diary estão definidos
            if not instance.activity or not instance.diary:
                raise ValidationError('Activity e Diary são obrigatórios para salvar worklog.')
            
            # Se já tem PK, é uma edição - salva normalmente
            if instance.pk:
                instance.save()
                logger.info(f"Worklog existente atualizado: {instance.id}")
            else:
                # É um novo worklog - verifica se já existe com mesma activity e diary
                # Usa get_or_create para evitar race conditions
                from django.db import IntegrityError
                try:
                    existing_worklog, created = DailyWorkLog.objects.get_or_create(
                        activity=instance.activity,
                        diary=instance.diary,
                        defaults={
                            'location': instance.location,
                            'work_stage': getattr(instance, 'work_stage', 'AN'),
                            'percentage_executed_today': instance.percentage_executed_today,
                            'accumulated_progress_snapshot': instance.accumulated_progress_snapshot,
                            'notes': instance.notes,
                        }
                    )
                    if created:
                        instance = existing_worklog
                        logger.info(f"Novo worklog criado: {instance.id}")
                    else:
                        # Já existe - atualiza o existente
                        existing_worklog.location = instance.location
                        existing_worklog.work_stage = getattr(instance, 'work_stage', 'AN')
                        existing_worklog.percentage_executed_today = instance.percentage_executed_today
                        existing_worklog.accumulated_progress_snapshot = instance.accumulated_progress_snapshot
                        existing_worklog.notes = instance.notes
                        existing_worklog.save()
                        instance = existing_worklog
                        logger.info(f"Worklog existente atualizado (evitou duplicata): {existing_worklog.id}")
                except IntegrityError:
                    # Fallback: se ainda assim houver erro (race condition), busca e atualiza
                    try:
                        existing_worklog = DailyWorkLog.objects.get(
                            activity=instance.activity,
                            diary=instance.diary
                        )
                        existing_worklog.location = instance.location
                        existing_worklog.work_stage = getattr(instance, 'work_stage', 'AN')
                        existing_worklog.percentage_executed_today = instance.percentage_executed_today
                        existing_worklog.accumulated_progress_snapshot = instance.accumulated_progress_snapshot
                        existing_worklog.notes = instance.notes
                        existing_worklog.save()
                        instance = existing_worklog
                        logger.info(f"Worklog existente atualizado após IntegrityError: {existing_worklog.id}")
                    except DailyWorkLog.DoesNotExist:
                        # Se não encontrou, tenta salvar novamente (pode ter sido criado entre as tentativas)
                        instance.save()
                        logger.info(f"Novo worklog criado após IntegrityError: {instance.id}")
        
        return instance


class LaborItemForm(forms.ModelForm):
    """Form para item de mão de obra (usado em formset)."""
    
    class Meta:
        model = Labor
        fields = ['name', 'role', 'hourly_rate']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none text-sm',
            }),
            'role': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none text-sm',
            }),
            'hourly_rate': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none text-sm',
                'step': '0.01',
                'min': '0',
            }),
        }


# Nota: Labor não tem FK direto para ConstructionDiary
# Mão de obra é gerenciada através de DailyWorkLog.resources_labor
# Não precisamos de formset para Labor aqui

class DiaryImageFormSetBase(forms.BaseInlineFormSet):
    """Formset customizado que ignora formulários completamente vazios."""
    
    def _should_delete_form(self, form):
        """Determina se um formulário deve ser deletado antes da validação."""
        # Se já está marcado para deletar, retorna True
        if hasattr(form, 'cleaned_data') and form.cleaned_data and form.cleaned_data.get('DELETE', False):
            return True
        
        # Verifica se o formulário está completamente vazio
        # Verifica os dados brutos do formulário ANTES da validação
        image = None
        caption = None
        
        # Tenta obter os dados do formulário
        if hasattr(form, 'cleaned_data') and form.cleaned_data:
            image = form.cleaned_data.get('image')
            caption_raw = form.cleaned_data.get('caption')
            # Trata strings vazias como None
            caption = caption_raw.strip() if caption_raw and isinstance(caption_raw, str) and caption_raw.strip() else None
        elif hasattr(form, 'data') and form.data:
            # Verifica os dados brutos antes da validação
            prefix = form.prefix if hasattr(form, 'prefix') and form.prefix else ''
            if prefix:
                image_key = f'{prefix}-image'
                caption_key = f'{prefix}-caption'
            else:
                image_key = 'image'
                caption_key = 'caption'
            
            # Verifica se há arquivo sendo enviado
            # IMPORTANTE: Verifica tanto em form.files quanto em form.data para capturar arquivos
            if hasattr(form, 'files') and form.files:
                image = form.files.get(image_key) if image_key in form.files else None
            # Se não encontrou em form.files, tenta verificar diretamente no request (via formset)
            if not image and hasattr(form, 'files') and form.files:
                # Tenta buscar por qualquer chave que contenha o prefixo
                for key in form.files.keys():
                    if image_key in key or key.endswith('-image'):
                        image = form.files.get(key)
                        break
            
            # Verifica se há legenda (trata strings vazias como None)
            caption_raw = form.data.get(caption_key, '') if caption_key in form.data else ''
            caption = caption_raw.strip() if caption_raw and isinstance(caption_raw, str) and caption_raw.strip() else None
        
        has_pk = form.instance.pk if hasattr(form, 'instance') and form.instance else False
        
        # Se está completamente vazio (sem imagem, sem legenda, sem pk), marca para deletar
        if not image and not caption and not has_pk:
            return True
        
        # Chama o método padrão para outros casos
        return super()._should_delete_form(form)
    
    def clean(self):
        """Remove formulários vazios da validação."""
        # Chama o clean() padrão primeiro
        super().clean()
        
        # Remove erros de formulários que foram marcados para deletar ou estão vazios
        for form in self.forms:
            # Se está marcado para deletar, remove erros
            if hasattr(form, 'cleaned_data') and form.cleaned_data and form.cleaned_data.get('DELETE', False):
                form._errors = {}
            # Se está completamente vazio, também remove erros
            elif hasattr(form, 'cleaned_data') and form.cleaned_data:
                image = form.cleaned_data.get('image')
                caption_raw = form.cleaned_data.get('caption')
                # Trata strings vazias como None
                caption = caption_raw.strip() if caption_raw and isinstance(caption_raw, str) and caption_raw.strip() else None
                has_pk = form.instance.pk if hasattr(form, 'instance') and form.instance else False
                if not image and not caption and not has_pk:
                    form._errors = {}
                    # Limpa o campo caption se estiver vazio
                    if 'caption' in form.cleaned_data and not caption:
                        form.cleaned_data['caption'] = None
                    if 'DELETE' in form.fields:
                        form.cleaned_data['DELETE'] = True

DiaryImageFormSet = inlineformset_factory(
    ConstructionDiary,
    DiaryImage,
    form=DiaryImageForm,
    formset=DiaryImageFormSetBase,
    extra=0,  # Não cria formulários vazios por padrão - fotos são adicionadas via JavaScript
    can_delete=True,
    fields=['image', 'caption', 'is_approved_for_report']
)

DailyWorkLogFormSet = inlineformset_factory(
    ConstructionDiary,
    DailyWorkLog,
    form=DailyWorkLogForm,
    extra=0,  # Não cria formulários vazios por padrão
    can_delete=True,
    # Não especifica fields para usar os campos definidos no form
)


class ProjectForm(forms.ModelForm):
    """Form para criação e edição de projetos."""
    
    class Meta:
        model = Project
        fields = [
            'name',
            'code',
            'description',
            'address',
            'responsible',
            'start_date',
            'end_date',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-1.5 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none',
                'placeholder': 'Ex.: Shopping Santa Luzia'
            }),
            'code': forms.TextInput(attrs={
                'class': 'w-full px-3 py-1.5 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none',
                'placeholder': 'Código único (ex: PROJ-2024-001)'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-3 py-1.5 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none',
                'placeholder': 'Descrição detalhada do projeto...'
            }),
            'address': forms.TextInput(attrs={
                'class': 'w-full px-3 py-1.5 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none',
                'placeholder': 'Ex.: Av. ABC, 100, Centro'
            }),
            'responsible': forms.TextInput(attrs={
                'class': 'w-full px-3 py-1.5 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none',
                'placeholder': 'Ex.: Eng. Carlos Silva'
            }),
            'start_date': forms.TextInput(attrs={
                'type': 'text',
                'class': 'w-full px-3 py-1.5 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none flatpickr-input',
                'placeholder': 'dd/mm/aaaa',
                'readonly': True
            }),
            'end_date': forms.TextInput(attrs={
                'type': 'text',
                'class': 'w-full px-3 py-1.5 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none flatpickr-input',
                'placeholder': 'dd/mm/aaaa',
                'readonly': True
            }),
        }
    
    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.upper().strip()
            # Verifica se já existe outro projeto com o mesmo código
            existing = Project.objects.filter(code=code)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError('Já existe um projeto com este código.')
        return code
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if end_date <= start_date:
                raise ValidationError({
                    'end_date': 'A data de término deve ser posterior à data de início.'
                })
        
        return cleaned_data


class ActivityForm(forms.ModelForm):
    """Form para criação e edição de atividades na EAP."""
    
    class Meta:
        model = Activity
        fields = [
            'name',
            'code',
            'description',
            'planned_start',
            'planned_end',
            'weight',
            'status',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'placeholder': 'Nome da atividade...'
            }),
            'code': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'placeholder': 'Código (ex: 1.2.1)'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'placeholder': 'Descrição da atividade...'
            }),
            'planned_start': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
            }),
            'planned_end': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
            }),
            'weight': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': '0.00'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
            }),
        }
    
    def clean_weight(self):
        weight = self.cleaned_data.get('weight')
        if weight is not None:
            if weight < 0 or weight > 100:
                raise ValidationError('O peso deve estar entre 0 e 100.')
        return weight
    
    def clean(self):
        cleaned_data = super().clean()
        planned_start = cleaned_data.get('planned_start')
        planned_end = cleaned_data.get('planned_end')
        
        if planned_start and planned_end:
            if planned_end < planned_start:
                raise ValidationError({
                    'planned_end': 'A data de término planejada deve ser posterior à data de início.'
                })
        
        return cleaned_data


class LaborForm(forms.ModelForm):
    """Form para criação e edição de mão de obra."""
    
    class Meta:
        model = Labor
        fields = [
            'name',
            'role',
            'role_custom',
            'labor_type',
            'company',
            'hourly_rate',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'placeholder': 'Nome do funcionário...'
            }),
            'role': forms.Select(attrs={
                'class': 'hidden',  # Escondido porque usamos radio buttons customizados no template
            }),
            'role_custom': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'placeholder': 'Cargo personalizado (se não estiver na lista)'
            }),
            'labor_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
            }),
            'company': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'placeholder': 'Nome da empresa (para terceiros)'
            }),
            'hourly_rate': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500',
            }),
        }


class EquipmentForm(forms.ModelForm):
    """Form para criação e edição de equipamentos."""
    
    class Meta:
        model = Equipment
        fields = [
            'name',
            'code',
            'equipment_type',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'placeholder': 'Nome do equipamento...'
            }),
            'code': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'placeholder': 'Código único do equipamento...'
            }),
            'equipment_type': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
                'placeholder': 'Tipo de equipamento (ex: Escavadeira, Betoneira)...'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500',
            }),
        }
    
    def clean_code(self):
        """Valida e normaliza o código do equipamento."""
        code = self.cleaned_data.get('code')
        if code:
            code = code.upper().strip()
            # Verifica se já existe outro equipamento com o mesmo código
            existing = Equipment.objects.filter(code=code)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError('Já existe um equipamento com este código.')
        return code


class ProfileEditForm(forms.Form):
    """Form para edição de perfil do usuário."""
    
    first_name = forms.CharField(
        max_length=150,
        required=False,
        label='Nome',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
            'placeholder': 'Seu primeiro nome'
        })
    )
    
    last_name = forms.CharField(
        max_length=150,
        required=False,
        label='Sobrenome',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
            'placeholder': 'Seu sobrenome'
        })
    )
    
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
            'placeholder': 'seu@email.com'
        })
    )
    
    new_password = forms.CharField(
        required=False,
        label='Nova Senha',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
            'placeholder': 'Deixe em branco para não alterar'
        }),
        help_text='Deixe em branco se não quiser alterar a senha.'
    )
    
    confirm_password = forms.CharField(
        required=False,
        label='Confirmar Nova Senha',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
            'placeholder': 'Confirme a nova senha'
        })
    )
    
    current_password = forms.CharField(
        required=False,
        label='Senha Atual (obrigatório para alterar senha)',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
            'placeholder': 'Digite sua senha atual'
        }),
        help_text='Necessário apenas se você quiser alterar a senha.'
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and self.user:
            # Verifica se o email já está em uso por outro usuário
            if User.objects.filter(email=email).exclude(pk=self.user.pk).exists():
                raise ValidationError('Este email já está em uso por outro usuário.')
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        current_password = cleaned_data.get('current_password')
        
        # Se o usuário quer alterar a senha
        if new_password or confirm_password:
            if not current_password:
                raise ValidationError({
                    'current_password': 'Você deve informar sua senha atual para alterar a senha.'
                })
            
            # Verifica se a senha atual está correta
            if self.user and not self.user.check_password(current_password):
                raise ValidationError({
                    'current_password': 'Senha atual incorreta.'
                })
            
            # Verifica se as novas senhas coincidem
            if new_password != confirm_password:
                raise ValidationError({
                    'confirm_password': 'As senhas não coincidem.'
                })
            
            # Valida a nova senha
            if new_password:
                try:
                    validate_password(new_password, self.user)
                except ValidationError as e:
                    raise ValidationError({
                        'new_password': e.messages
                    })
        
        return cleaned_data
    
    def save(self):
        """Salva as alterações no usuário."""
        if not self.user:
            return None
        
        user = self.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        
        # Altera a senha se fornecida
        if self.cleaned_data.get('new_password'):
            user.set_password(self.cleaned_data['new_password'])
        
        user.save()
        return user


class DiaryOccurrenceForm(forms.ModelForm):
    """Form para DiaryOccurrence com suporte a tags."""
    
    class Meta:
        model = DiaryOccurrence
        fields = ['description', 'tags']
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 2,
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none max-h-24',
                'placeholder': 'Descreva a ocorrência...',
            }),
            'tags': forms.SelectMultiple(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:border-transparent outline-none',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtra apenas tags ativas
        self.fields['tags'].queryset = OccurrenceTag.objects.filter(is_active=True)
        self.fields['tags'].required = False
        self.fields['description'].required = True


# Formset para ocorrências
DiaryOccurrenceFormSet = inlineformset_factory(
    ConstructionDiary,
    DiaryOccurrence,
    form=DiaryOccurrenceForm,
    extra=0,
    can_delete=True,
    fields=['description', 'tags']
)

