from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = 'Cria os grupos de usuários e suas permissões'

    def handle(self, *args, **options):
        # Grupos
        grupos = {
            'CHEFIA': {
                'description': 'Visualiza tudo, somente leitura, acessa dashboard, pode marcar "Não Aplica"',
            },
            'ENGENHARIA': {
                'description': 'Edita planejamento (local, prazo, quantidade, responsável, prioridade)',
            },
        }

        for nome, info in grupos.items():
            grupo, created = Group.objects.get_or_create(name=nome)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Grupo "{nome}" criado com sucesso.'))
            else:
                self.stdout.write(self.style.WARNING(f'Grupo "{nome}" já existe.'))

        # Permissões específicas (se necessário, adicionar depois)
        self.stdout.write(self.style.SUCCESS('Grupos criados/verificados com sucesso!'))

