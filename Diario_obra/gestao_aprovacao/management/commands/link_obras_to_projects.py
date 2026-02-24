"""
Vincular Obras (GestControll) aos Projetos (Diário de Obra) para lista única de obras no sistema.
Caso o código da obra (Obra.codigo) coincida com o código do projeto (Project.code), o vínculo é feito.

Uso:
    python manage.py link_obras_to_projects
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from gestao_aprovacao.models import Obra
from core.models import Project


class Command(BaseCommand):
    help = 'Vincula Obras ao Project pelo código (Obra.codigo = Project.code) para unificar acesso'

    def handle(self, *args, **options):
        updated = 0
        not_found = []
        with transaction.atomic():
            for obra in Obra.objects.filter(ativo=True).select_related('project'):
                if obra.project_id:
                    continue
                project = Project.objects.filter(code=obra.codigo, is_active=True).first()
                if project:
                    obra.project = project
                    obra.save(update_fields=['project'])
                    updated += 1
                    self.stdout.write(f'  Vinculado: {obra.codigo} -> Project {project.code} - {project.name}')
                else:
                    not_found.append(obra.codigo)
        self.stdout.write(self.style.SUCCESS(f'Vinculadas {updated} obra(s).'))
        if not_found:
            self.stdout.write(
                self.style.WARNING(
                    f'Obras sem projeto correspondente (cadastre o projeto no Diário ou vincule manualmente no admin): {", ".join(not_found)}'
                )
            )
