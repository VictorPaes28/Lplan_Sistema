"""
Serializers DRF para Diário de Obra V2.0 - LPLAN

Serializers para todos os modelos com validações e relacionamentos.
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Project,
    Activity,
    ConstructionDiary,
    DiaryImage,
    DailyWorkLog,
    Labor,
    Equipment,
    ActivityStatus,
    DiaryStatus,
)


class UserSerializer(serializers.ModelSerializer):
    """Serializer para User (apenas campos essenciais)."""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name']
        read_only_fields = ['id', 'username', 'email', 'first_name', 'last_name']
    
    def get_full_name(self, obj):
        """Retorna nome completo ou username."""
        return obj.get_full_name() or obj.username


class ProjectSerializer(serializers.ModelSerializer):
    """Serializer para Project."""
    activities_count = serializers.SerializerMethodField()
    diaries_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'name', 'code', 'description', 'start_date', 'end_date',
            'is_active', 'created_at', 'updated_at', 'activities_count', 'diaries_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_activities_count(self, obj):
        """Retorna número de atividades do projeto."""
        return obj.activities.count()
    
    def get_diaries_count(self, obj):
        """Retorna número de diários do projeto."""
        return obj.diaries.count()


class ActivityTreeSerializer(serializers.ModelSerializer):
    """
    Serializer para Activity com suporte a hierarquia.
    
    Usado para visualização de árvore EAP com carregamento preguiçoso.
    """
    children_count = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    parent_id = serializers.SerializerMethodField()
    
    class Meta:
        model = Activity
        fields = [
            'id', 'name', 'code', 'description', 'planned_start', 'planned_end',
            'weight', 'status', 'project', 'parent_id', 'children_count', 'progress',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'progress']
    
    def get_children_count(self, obj):
        """Retorna número de filhos diretos."""
        return obj.numchild
    
    def get_progress(self, obj):
        """Retorna progresso calculado da atividade."""
        from .services import ProgressService
        try:
            return float(ProgressService.get_activity_progress(obj))
        except Exception:
            return 0.0
    
    def get_parent_id(self, obj):
        """Retorna ID do pai ou None se for raiz."""
        if obj.is_root():
            return None
        return obj.get_parent().id


class ActivityDetailSerializer(ActivityTreeSerializer):
    """
    Serializer detalhado para Activity.
    
    Inclui informações de filhos e ancestrais.
    """
    children = serializers.SerializerMethodField()
    ancestors = serializers.SerializerMethodField()
    work_logs_count = serializers.SerializerMethodField()
    
    class Meta(ActivityTreeSerializer.Meta):
        fields = ActivityTreeSerializer.Meta.fields + [
            'children', 'ancestors', 'work_logs_count'
        ]
    
    def get_children(self, obj):
        """Retorna filhos diretos (limitado para performance)."""
        children = obj.get_children()[:50]  # Limite para evitar sobrecarga
        return ActivityTreeSerializer(children, many=True).data
    
    def get_ancestors(self, obj):
        """Retorna ancestrais."""
        ancestors = obj.get_ancestors()
        return ActivityTreeSerializer(ancestors, many=True).data
    
    def get_work_logs_count(self, obj):
        """Retorna número de registros de trabalho."""
        return obj.work_logs.count()


class LaborSerializer(serializers.ModelSerializer):
    """Serializer para Labor."""
    class Meta:
        model = Labor
        fields = ['id', 'name', 'role', 'hourly_rate', 'is_active']
        read_only_fields = ['id']


class EquipmentSerializer(serializers.ModelSerializer):
    """Serializer para Equipment."""
    class Meta:
        model = Equipment
        fields = ['id', 'name', 'code', 'equipment_type', 'is_active']
        read_only_fields = ['id']


class DiaryImageSerializer(serializers.ModelSerializer):
    """Serializer para DiaryImage."""
    image_url = serializers.SerializerMethodField()
    pdf_optimized_url = serializers.SerializerMethodField()
    
    class Meta:
        model = DiaryImage
        fields = [
            'id', 'diary', 'image', 'image_url', 'pdf_optimized', 'pdf_optimized_url',
            'caption', 'is_approved_for_report', 'uploaded_at'
        ]
        read_only_fields = ['id', 'uploaded_at']
    
    def get_image_url(self, obj):
        """Retorna URL da imagem original."""
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None
    
    def get_pdf_optimized_url(self, obj):
        """Retorna URL da imagem otimizada."""
        if obj.pdf_optimized:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.pdf_optimized.url)
            return obj.pdf_optimized.url
        return None


class DailyWorkLogSerializer(serializers.ModelSerializer):
    """Serializer para DailyWorkLog."""
    activity_code = serializers.CharField(source='activity.code', read_only=True)
    activity_name = serializers.CharField(source='activity.name', read_only=True)
    resources_labor_names = serializers.SerializerMethodField()
    resources_equipment_names = serializers.SerializerMethodField()
    
    class Meta:
        model = DailyWorkLog
        fields = [
            'id', 'activity', 'activity_code', 'activity_name', 'diary',
            'percentage_executed_today', 'accumulated_progress_snapshot', 'notes',
            'resources_labor', 'resources_labor_names',
            'resources_equipment', 'resources_equipment_names',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_resources_labor_names(self, obj):
        """Retorna nomes dos recursos de mão de obra."""
        return [str(labor) for labor in obj.resources_labor.all()]
    
    def get_resources_equipment_names(self, obj):
        """Retorna nomes dos equipamentos."""
        return [str(equipment) for equipment in obj.resources_equipment.all()]


class ConstructionDiarySerializer(serializers.ModelSerializer):
    """Serializer para ConstructionDiary."""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True, allow_null=True)
    images_count = serializers.SerializerMethodField()
    work_logs_count = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    
    class Meta:
        model = ConstructionDiary
        fields = [
            'id', 'project', 'date', 'status', 'created_by', 'created_by_name',
            'reviewed_by', 'reviewed_by_name', 'approved_at', 'weather_conditions',
            'general_notes', 'images_count', 'work_logs_count', 'can_edit',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'approved_at', 'reviewed_by',
            'images_count', 'work_logs_count', 'can_edit'
        ]
    
    def get_images_count(self, obj):
        """Retorna número de imagens aprovadas para relatório."""
        return obj.images.filter(is_approved_for_report=True).count()
    
    def get_work_logs_count(self, obj):
        """Retorna número de registros de trabalho."""
        return obj.work_logs.count()
    
    def get_can_edit(self, obj):
        """Verifica se o diário pode ser editado pelo usuário atual."""
        request = self.context.get('request')
        if request and request.user:
            return obj.can_be_edited_by(request.user)
        return False
    
    def validate(self, data):
        """Validações customizadas."""
        # Valida que diário aprovado não pode ser editado
        if self.instance and self.instance.is_approved():
            raise serializers.ValidationError(
                "Diários aprovados não podem ser editados."
            )
        
        # Valida unicidade de projeto + data
        if 'project' in data or 'date' in data:
            project = data.get('project', self.instance.project if self.instance else None)
            date = data.get('date', self.instance.date if self.instance else None)
            
            if project and date:
                existing = ConstructionDiary.objects.filter(
                    project=project,
                    date=date
                )
                if self.instance:
                    existing = existing.exclude(pk=self.instance.pk)
                
                if existing.exists():
                    raise serializers.ValidationError(
                        "Já existe um diário para este projeto nesta data."
                    )
        
        return data


class ConstructionDiaryDetailSerializer(ConstructionDiarySerializer):
    """
    Serializer detalhado para ConstructionDiary.
    
    Inclui imagens e registros de trabalho.
    """
    images = DiaryImageSerializer(many=True, read_only=True)
    work_logs = DailyWorkLogSerializer(many=True, read_only=True)
    
    class Meta(ConstructionDiarySerializer.Meta):
        fields = ConstructionDiarySerializer.Meta.fields + ['images', 'work_logs']

