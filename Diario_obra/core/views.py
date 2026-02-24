"""
ViewSets DRF para Diário de Obra V2.0 - LPLAN

ViewSets com permissões customizadas e ações específicas para workflow.
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.http import HttpResponse, FileResponse, HttpResponseRedirect
from django.core.exceptions import ValidationError, PermissionDenied
import os

from .models import (
    Project,
    Activity,
    ConstructionDiary,
    DiaryImage,
    DailyWorkLog,
    Labor,
    Equipment,
    DiaryStatus,
)
from .serializers import (
    ProjectSerializer,
    ActivityTreeSerializer,
    ActivityDetailSerializer,
    ConstructionDiarySerializer,
    ConstructionDiaryDetailSerializer,
    DiaryImageSerializer,
    DailyWorkLogSerializer,
    LaborSerializer,
    EquipmentSerializer,
)
from .permissions import CanApproveDiary, CanEditDiary
from .services import ProgressService


class ProjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet para Project.
    
    Permite CRUD completo de projetos.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'code']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['created_at', 'name', 'code']
    ordering = ['-created_at']
    
    @action(detail=True, methods=['get'])
    def activities_tree(self, request, pk=None):
        """
        Retorna árvore de atividades do projeto (raízes apenas).
        
        Usado para carregamento preguiçoso - retorna apenas o primeiro nível.
        """
        project = self.get_object()
        root_activities = Activity.objects.filter(
            project=project,
            depth=1
        ).order_by('code')
        
        serializer = ActivityTreeSerializer(root_activities, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def overall_progress(self, request, pk=None):
        """Retorna progresso geral do projeto."""
        project = self.get_object()
        progress = ProgressService.get_project_overall_progress(project.id)
        return Response({'progress': float(progress)})


class ActivityViewSet(viewsets.ModelViewSet):
    """
    ViewSet para Activity com suporte a hierarquia.
    
    Implementa carregamento preguiçoso de filhos.
    """
    queryset = Activity.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['project', 'status']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['code', 'name', 'created_at']
    ordering = ['code']
    
    def get_serializer_class(self):
        """Retorna serializer apropriado baseado na ação."""
        if self.action == 'retrieve':
            return ActivityDetailSerializer
        return ActivityTreeSerializer
    
    def get_queryset(self):
        """Filtra atividades por projeto se fornecido."""
        queryset = super().get_queryset()
        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset
    
    @action(detail=True, methods=['get'])
    def children(self, request, pk=None):
        """
        Retorna filhos diretos de uma atividade.
        
        Usado para carregamento preguiçoso da árvore EAP.
        """
        activity = self.get_object()
        children = activity.get_children().order_by('code')
        serializer = ActivityTreeSerializer(children, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """Retorna progresso atual da atividade."""
        activity = self.get_object()
        progress = ProgressService.get_activity_progress(activity)
        return Response({
            'activity_id': activity.id,
            'activity_code': activity.code,
            'progress': float(progress),
            'status': activity.status
        })
    
    @action(detail=True, methods=['post'])
    def recalculate_progress(self, request, pk=None):
        """Recalcula progresso da atividade e propaga para ancestrais."""
        activity = self.get_object()
        try:
            new_progress = ProgressService.calculate_rollup_progress(activity.id)
            return Response({
                'activity_id': activity.id,
                'new_progress': float(new_progress),
                'status': activity.status
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ConstructionDiaryViewSet(viewsets.ModelViewSet):
    """
    ViewSet para ConstructionDiary com workflow de aprovação.
    
    Implementa transições de estado e controle de permissões.
    
    NOTA: Esta view só deve responder a requisições que venham de /api/diaries/.
    Requisições do frontend (/diaries/) devem ser tratadas por diary_detail_view.
    """
    queryset = ConstructionDiary.objects.select_related(
        'project', 'created_by', 'reviewed_by'
    ).prefetch_related('images', 'work_logs').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['project', 'status', 'date']
    search_fields = ['general_notes', 'weather_conditions', 'project__code']
    ordering_fields = ['date', 'created_at', 'status']
    ordering = ['-date', '-created_at']
    
    def dispatch(self, request, *args, **kwargs):
        """Aceita /api/diario/diaries/ (lplan_central) e /api/diaries/ (diario_obra)."""
        path = request.path
        if not (path.startswith('/api/diario/diaries') or path.startswith('/api/diaries/')):
            from django.http import HttpResponseNotFound
            return HttpResponseNotFound("Esta rota não existe na API. Use /diaries/ para o frontend.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_serializer_class(self):
        """Retorna serializer apropriado baseado na ação."""
        if self.action == 'retrieve':
            return ConstructionDiaryDetailSerializer
        return ConstructionDiarySerializer
    
    def get_permissions(self):
        """Aplica permissões customizadas baseado na ação."""
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), CanEditDiary()]
        return [IsAuthenticated()]
    
    def get_queryset(self):
        """Filtra diários baseado em permissões do usuário."""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Usuários normais veem apenas seus próprios diários ou aprovados
        if not (user.is_staff or user.has_perm('core.can_approve_diary')):
            queryset = queryset.filter(
                Q(created_by=user) | Q(status=DiaryStatus.APROVADO)
            )
        
        return queryset
    
    def retrieve(self, request, *args, **kwargs):
        """Se for acesso no navegador (HTML), redireciona para a página do frontend."""
        pk = kwargs.get('pk')
        accept = request.META.get('HTTP_ACCEPT', '')
        # Navegador pedindo HTML ou link direto para /api/diario/diaries/<id> -> vai para o frontend
        if 'text/html' in accept or request.path.startswith('/api/diario/'):
            return HttpResponseRedirect(f'/diaries/{pk}/')
        return super().retrieve(request, *args, **kwargs)
    
    @action(detail=True, methods=['get', 'post'])
    def generate_pdf(self, request, pk=None):
        """
        Gera PDF do diário.
        
        GET: Retorna PDF diretamente (síncrono)
        POST: Dispara geração assíncrona via Celery
        """
        diary = self.get_object()
        
        if request.method == 'POST':
            # Geração assíncrona (se Celery estiver disponível)
            try:
                from .tasks import generate_diary_pdf_task, CELERY_AVAILABLE
                if CELERY_AVAILABLE:
                    task = generate_diary_pdf_task.delay(diary.id)
                    return Response({
                        'task_id': task.id,
                        'status': 'Generating PDF asynchronously',
                        'diary_id': diary.id
                    })
            except ImportError:
                pass
            # Fallback para geração síncrona se Celery não estiver disponível
            return Response({
                'error': 'Celery não está disponível. Use GET para geração síncrona.',
                'diary_id': diary.id
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        else:
            # Geração síncrona (para testes ou downloads imediatos)
            try:
                from core.utils.pdf_generator import PDFGenerator, WEASYPRINT_AVAILABLE
                
                if not WEASYPRINT_AVAILABLE:
                    return Response(
                        {'error': 'WeasyPrint não está disponível. No Windows, instale GTK+ ou use uma alternativa.'},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE
                    )
                
                pdf_bytes = PDFGenerator.generate_diary_pdf(diary.id)
                if pdf_bytes:
                    response = HttpResponse(
                        pdf_bytes.getvalue(),
                        content_type='application/pdf'
                    )
                    filename = f"diario_{diary.project.code}_{diary.date.strftime('%Y%m%d')}.pdf"
                    response['Content-Disposition'] = f'attachment; filename="{filename}"'
                    return response
                else:
                    return Response(
                        {'error': 'Failed to generate PDF'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            except (ImportError, OSError) as e:
                return Response(
                    {'error': f'WeasyPrint não está disponível: {str(e)}'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )


class DiaryImageViewSet(viewsets.ModelViewSet):
    """
    ViewSet para DiaryImage.
    
    Permite upload e gerenciamento de imagens do diário.
    """
    queryset = DiaryImage.objects.select_related('diary').all()
    serializer_class = DiaryImageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['diary', 'is_approved_for_report']
    ordering_fields = ['uploaded_at']
    ordering = ['-uploaded_at']
    
    def get_queryset(self):
        """Filtra imagens baseado em permissões."""
        queryset = super().get_queryset()
        diary_id = self.request.query_params.get('diary')
        if diary_id:
            queryset = queryset.filter(diary_id=diary_id)
        return queryset
    
    @action(detail=True, methods=['post'])
    def toggle_approval(self, request, pk=None):
        """
        Alterna is_approved_for_report da imagem.
        
        Permite ocultar/mostrar imagem no PDF sem deletá-la.
        """
        image = self.get_object()
        # Verifica permissão de edição do diário
        if not image.diary.can_be_edited_by(request.user):
            return Response(
                {'error': 'Você não tem permissão para editar este diário.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        image.is_approved_for_report = not image.is_approved_for_report
        image.save()
        serializer = self.get_serializer(image)
        return Response(serializer.data)


class DailyWorkLogViewSet(viewsets.ModelViewSet):
    """
    ViewSet para DailyWorkLog.
    
    Permite CRUD de registros de trabalho diário.
    """
    queryset = DailyWorkLog.objects.select_related(
        'activity', 'diary'
    ).prefetch_related('resources_labor', 'resources_equipment').all()
    serializer_class = DailyWorkLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['activity', 'diary']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def perform_create(self, serializer):
        """Cria work log e dispara recálculo de progresso."""
        work_log = serializer.save()
        # Dispara recálculo de progresso (já feito via signals, mas garantimos)
        try:
            ProgressService.update_activity_progress_from_worklog(work_log)
        except Exception:
            pass  # Log já foi salvo, erro no progresso não deve impedir
    
    def perform_update(self, serializer):
        """Atualiza work log e dispara recálculo de progresso."""
        work_log = serializer.save()
        try:
            ProgressService.update_activity_progress_from_worklog(work_log)
        except Exception:
            pass


class LaborViewSet(viewsets.ModelViewSet):
    """ViewSet para Labor."""
    queryset = Labor.objects.all()
    serializer_class = LaborSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active', 'role']
    search_fields = ['name', 'role']


class EquipmentViewSet(viewsets.ModelViewSet):
    """ViewSet para Equipment."""
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active', 'equipment_type']
    search_fields = ['name', 'code', 'equipment_type']

