"""
Cadastra as tags de ocorrências (OccurrenceTag) no banco.

Uso no servidor (após migrate):
    python manage.py seed_occurrence_tags

Usa get_or_create, então é seguro rodar mais de uma vez.
"""
from django.core.management.base import BaseCommand
from core.models import OccurrenceTag


# Lista (nome, cor hex) das tags de ocorrência a criar
TAGS_OCORRENCIA = [
    ('Atraso', '#EF4444'),
    ('Material', '#F59E0B'),
    ('Segurança', '#10B981'),
    ('Qualidade', '#3B82F6'),
    ('Clima', '#8B5CF6'),
    ('Fornecedor', '#EC4899'),
    ('Mão de obra', '#06B6D4'),
    ('Equipamento', '#84CC16'),
    ('Documentação', '#6366F1'),
    ('Outros', '#64748B'),
]


class Command(BaseCommand):
    help = 'Cadastra as tags de ocorrências (OccurrenceTag) no banco.'

    def handle(self, *args, **options):
        created = 0
        for name, color in TAGS_OCORRENCIA:
            _, was_created = OccurrenceTag.objects.get_or_create(
                name=name,
                defaults={'color': color, 'is_active': True}
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'  Criada: {name}'))
        if created == 0:
            self.stdout.write('Nenhuma tag nova criada (todas já existem).')
        else:
            self.stdout.write(self.style.SUCCESS(f'Total: {created} tag(s) criada(s).'))
