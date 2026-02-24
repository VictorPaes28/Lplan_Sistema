"""
Verificação pré-deploy: contagens por modelo e detecção de duplicatas.

Uso:
    python manage.py verificar_pre_deploy
    python manage.py verificar_pre_deploy --quiet

Verifica:
- Contagens: Project, ConstructionDiary, User (ativo), DiaryOccurrence, etc.
- Duplicatas: ConstructionDiary (project+date), DailyWorkLog (activity+diary).
- Órfãos: DiaryOccurrence/DiaryImage etc. referenciando diário inexistente (não aplicável se FK com CASCADE).
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Count

from core.models import (
    Project,
    ConstructionDiary,
    DiaryOccurrence,
    DailyWorkLog,
    DiaryImage,
    DiaryStatus,
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Verificação pré-deploy: contagens e duplicatas (core)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Apenas erros/avisos (sem contagens)',
        )

    def handle(self, *args, **options):
        quiet = options.get('quiet', False)
        errors = []
        warnings = []

        # Contagens
        if not quiet:
            self.stdout.write(self.style.SUCCESS('=== CONTAGENS (Diario_obra core) ==='))
            self.stdout.write(f'  Project: {Project.objects.count()}')
            self.stdout.write(f'  ConstructionDiary: {ConstructionDiary.objects.count()}')
            self.stdout.write(f'  DiaryOccurrence: {DiaryOccurrence.objects.count()}')
            self.stdout.write(f'  DailyWorkLog: {DailyWorkLog.objects.count()}')
            self.stdout.write(f'  DiaryImage: {DiaryImage.objects.count()}')
            self.stdout.write(f'  User (is_active=True): {User.objects.filter(is_active=True).count()}')

        # Duplicatas: project + date (ConstructionDiary)
        dup_diary = (
            ConstructionDiary.objects.values('project', 'date')
            .annotate(c=Count('id'))
            .filter(c__gt=1)
        )
        dup_list = list(dup_diary)
        if dup_list:
            errors.append(f'ConstructionDiary duplicado (project+date): {len(dup_list)} grupo(s)')
            for g in dup_list:
                self.stdout.write(self.style.ERROR(
                    f'  project_id={g["project"]} date={g["date"]} count={g["c"]}'
                ))
        elif not quiet:
            self.stdout.write(self.style.SUCCESS('  ConstructionDiary: nenhuma duplicata (project+date)'))

        # Duplicatas: activity + diary (DailyWorkLog)
        dup_worklog = (
            DailyWorkLog.objects.values('activity', 'diary')
            .annotate(c=Count('id'))
            .filter(c__gt=1)
        )
        dup_wl_list = list(dup_worklog)
        if dup_wl_list:
            warnings.append(f'DailyWorkLog duplicado (activity+diary): {len(dup_wl_list)} grupo(s)')
            for g in dup_wl_list[:10]:
                self.stdout.write(self.style.WARNING(
                    f'  activity_id={g["activity"]} diary_id={g["diary"]} count={g["c"]}'
                ))
            if len(dup_wl_list) > 10:
                self.stdout.write(self.style.WARNING(f'  ... e mais {len(dup_wl_list) - 10}'))
        elif not quiet:
            self.stdout.write(self.style.SUCCESS('  DailyWorkLog: nenhuma duplicata (activity+diary)'))

        # Resumo
        self.stdout.write('')
        if errors:
            for e in errors:
                self.stdout.write(self.style.ERROR(f'ERRO: {e}'))
        if warnings:
            for w in warnings:
                self.stdout.write(self.style.WARNING(f'AVISO: {w}'))
        if not errors and not warnings and quiet:
            self.stdout.write(self.style.SUCCESS('Nenhuma duplicata encontrada.'))
        if errors:
            raise SystemExit(1)
