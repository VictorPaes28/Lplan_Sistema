"""
Context processors para disponibilizar dados globais em todos os templates.
"""
from .models import (
    ConstructionDiary,
    DiaryImage,
    Activity,
    DiaryVideo,
    DiaryAttachment,
    DiaryOccurrence,
)


def sidebar_counters(request):
    """
    Context processor para adicionar contadores da sidebar em todas as páginas.
    """
    # Se não houver projeto selecionado, retorna contadores zerados
    if not request.user.is_authenticated:
        return {
            'total_reports_count': 0,
            'total_photos_count': 0,
            'total_videos_count': 0,
            'total_activities_count': 0,
            'total_occurrences_count': 0,
            'total_comments_count': 0,
            'total_attachments_count': 0,
        }
    
    project_id = request.session.get('selected_project_id')
    
    if not project_id:
        return {
            'total_reports_count': 0,
            'total_photos_count': 0,
            'total_videos_count': 0,
            'total_activities_count': 0,
            'total_occurrences_count': 0,
            'total_comments_count': 0,
            'total_attachments_count': 0,
        }
    
    try:
        # Total de relatórios
        total_reports = ConstructionDiary.objects.filter(project_id=project_id).count()
        
        # Total de fotos
        total_photos = DiaryImage.objects.filter(
            diary__project_id=project_id,
            is_approved_for_report=True
        ).count()
        
        # Total de vídeos
        total_videos = DiaryVideo.objects.filter(
            diary__project_id=project_id
        ).count()
        
        # Total de atividades
        total_activities = Activity.objects.filter(project_id=project_id).count()
        
        # Total de ocorrências (modelo DiaryOccurrence – mesmo do dashboard e aba Ocorrências)
        total_occurrences = DiaryOccurrence.objects.filter(
            diary__project_id=project_id
        ).count()
        
        # Total de comentários (diários com general_notes)
        total_comments = ConstructionDiary.objects.filter(
            project_id=project_id
        ).exclude(general_notes='').exclude(general_notes__isnull=True).count()
        
        # Total de anexos
        total_attachments = DiaryAttachment.objects.filter(
            diary__project_id=project_id
        ).count()
        
        return {
            'total_reports_count': total_reports,
            'total_photos_count': total_photos,
            'total_videos_count': total_videos,
            'total_activities_count': total_activities,
            'total_occurrences_count': total_occurrences,
            'total_comments_count': total_comments,
            'total_attachments_count': total_attachments,
        }
    except Exception:
        # Em caso de erro, retorna contadores zerados
        return {
            'total_reports_count': 0,
            'total_photos_count': 0,
            'total_videos_count': 0,
            'total_activities_count': 0,
            'total_occurrences_count': 0,
            'total_comments_count': 0,
            'total_attachments_count': 0,
        }

