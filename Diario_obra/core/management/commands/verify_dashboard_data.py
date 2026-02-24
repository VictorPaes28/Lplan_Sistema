"""
Script para verificar se os dados do dashboard estão corretos.
Compara o que está no banco com o que o dashboard deveria mostrar.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import (
    Project,
    ConstructionDiary,
    DiaryImage,
    DiaryVideo,
    DiaryAttachment,
    DiaryOccurrence,
    OccurrenceTag,
    Activity,
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Verifica se os dados do dashboard estão corretos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--project-id',
            type=int,
            help='ID do projeto a verificar'
        )

    def handle(self, *args, **options):
        project_id = options.get('project_id')
        
        if project_id:
            try:
                project = Project.objects.get(pk=project_id)
            except Project.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Projeto com ID {project_id} não encontrado.'))
                return
        else:
            project = Project.objects.first()
            if not project:
                self.stdout.write(self.style.ERROR('Nenhum projeto encontrado.'))
                return
        
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('VERIFICAÇÃO DE DADOS DO DASHBOARD'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(f'\nProjeto: {project.name} (ID: {project.id})\n')
        
        # 1. Verifica ocorrências
        self.stdout.write('\n' + self.style.SUCCESS('1. OCORRÊNCIAS'))
        self.stdout.write('-'*70)
        
        # Como o dashboard busca
        dashboard_occurrences = DiaryOccurrence.objects.filter(
            diary__project=project
        ).count()
        
        # Todas as ocorrências (para debug)
        all_occurrences = DiaryOccurrence.objects.all()
        all_occurrences_with_project = DiaryOccurrence.objects.filter(
            diary__project=project
        )
        
        self.stdout.write(f'  Dashboard deveria mostrar: {dashboard_occurrences}')
        self.stdout.write(f'  Total no banco: {all_occurrences.count()}')
        self.stdout.write(f'  Ocorrências do projeto {project.name}: {all_occurrences_with_project.count()}')
        
        if all_occurrences_with_project.exists():
            self.stdout.write('\n  Detalhes das ocorrências:')
            for occ in all_occurrences_with_project:
                self.stdout.write(f'    - ID={occ.id}, Diário ID={occ.diary.id}, Data={occ.diary.date}, Projeto={occ.diary.project.name}')
        else:
            self.stdout.write(self.style.WARNING('  ⚠ Nenhuma ocorrência encontrada para este projeto'))
            
            # Verifica se há ocorrências em outros projetos
            other_occurrences = DiaryOccurrence.objects.exclude(diary__project=project)
            if other_occurrences.exists():
                self.stdout.write(f'\n  ⚠ Encontradas {other_occurrences.count()} ocorrências em OUTROS projetos:')
                for occ in other_occurrences[:5]:
                    self.stdout.write(f'    - ID={occ.id}, Diário ID={occ.diary.id}, Projeto={occ.diary.project.name}')
        
        # 2. Verifica vídeos
        self.stdout.write('\n' + self.style.SUCCESS('2. VÍDEOS'))
        self.stdout.write('-'*70)
        
        # Como o dashboard busca
        dashboard_videos = DiaryVideo.objects.filter(
            diary__project=project
        ).count()
        
        recent_videos = list(DiaryVideo.objects.filter(
            diary__project=project
        ).select_related('diary').order_by('-uploaded_at')[:6])
        
        # Todas as vídeos (para debug)
        all_videos = DiaryVideo.objects.all()
        all_videos_with_project = DiaryVideo.objects.filter(
            diary__project=project
        )
        
        self.stdout.write(f'  Dashboard deveria mostrar: {dashboard_videos} vídeos')
        self.stdout.write(f'  Vídeos recentes (últimos 6): {len(recent_videos)}')
        self.stdout.write(f'  Total no banco: {all_videos.count()}')
        self.stdout.write(f'  Vídeos do projeto {project.name}: {all_videos_with_project.count()}')
        
        if all_videos_with_project.exists():
            self.stdout.write('\n  Detalhes dos vídeos:')
            for video in all_videos_with_project:
                self.stdout.write(f'    - ID={video.id}, Diário ID={video.diary.id}, Data={video.diary.date}, Projeto={video.diary.project.name}, Caption={video.caption[:50] if video.caption else "Sem legenda"}')
        else:
            self.stdout.write(self.style.WARNING('  ⚠ Nenhum vídeo encontrado para este projeto'))
            
            # Verifica se há vídeos em outros projetos
            other_videos = DiaryVideo.objects.exclude(diary__project=project)
            if other_videos.exists():
                self.stdout.write(f'\n  ⚠ Encontrados {other_videos.count()} vídeos em OUTROS projetos:')
                for video in other_videos[:5]:
                    self.stdout.write(f'    - ID={video.id}, Diário ID={video.diary.id}, Projeto={video.diary.project.name}')
        
        # 3. Verifica relatórios recentes
        self.stdout.write('\n' + self.style.SUCCESS('3. RELATÓRIOS RECENTES'))
        self.stdout.write('-'*70)
        
        recent_reports = list(ConstructionDiary.objects.filter(
            project=project
        ).select_related('project').prefetch_related('images').order_by('-date', '-created_at')[:7])
        
        self.stdout.write(f'  Relatórios recentes: {len(recent_reports)}')
        
        if recent_reports:
            self.stdout.write('\n  Detalhes dos relatórios:')
            for report in recent_reports:
                images_count = report.images.count()
                videos_count = report.videos.count()
                occurrences_count = report.occurrences.count()
                self.stdout.write(f'    - ID={report.id}, Data={report.date}, Fotos={images_count}, Vídeos={videos_count}, Ocorrências={occurrences_count}')
        
        # 4. Resumo
        self.stdout.write('\n' + self.style.SUCCESS('4. RESUMO'))
        self.stdout.write('-'*70)
        self.stdout.write(f'  Total de relatórios: {ConstructionDiary.objects.filter(project=project).count()}')
        self.stdout.write(f'  Total de fotos: {DiaryImage.objects.filter(diary__project=project).count()}')
        self.stdout.write(f'  Total de vídeos: {DiaryVideo.objects.filter(diary__project=project).count()}')
        self.stdout.write(f'  Total de ocorrências: {DiaryOccurrence.objects.filter(diary__project=project).count()}')
        self.stdout.write(f'  Total de anexos: {DiaryAttachment.objects.filter(diary__project=project).count()}')
        
        # Verifica se há discrepância
        if dashboard_occurrences == 0 and all_occurrences_with_project.exists():
            self.stdout.write(self.style.ERROR('\n  ✗ PROBLEMA: Dashboard mostra 0 mas há ocorrências no banco!'))
        
        if dashboard_videos == 0 and all_videos_with_project.exists():
            self.stdout.write(self.style.ERROR('\n  ✗ PROBLEMA: Dashboard mostra 0 mas há vídeos no banco!'))
        
        if len(recent_videos) == 0 and all_videos_with_project.exists():
            self.stdout.write(self.style.ERROR('\n  ✗ PROBLEMA: Dashboard não mostra vídeos recentes mas há vídeos no banco!'))
        
        self.stdout.write('\n' + '='*70)
