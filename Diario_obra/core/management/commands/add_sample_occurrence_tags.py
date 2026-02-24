"""
Management command para adicionar tags de ocorrências padrão ao sistema.
Desativa tags obsoletas (ex.: Teste automatizado, repetidas) e cria/atualiza a lista curada.
"""
from django.core.management.base import BaseCommand
from core.models import OccurrenceTag


# Tags a desativar (não aparecem mais na lista; existentes no banco ficam is_active=False)
TAGS_TO_DEACTIVATE = [
    'Teste automatizado',
    'Teste Automatizado',
    'teste automatizado',
    'Dia Chuvoso',  # redundante com "Condição climática adversa"
]


class Command(BaseCommand):
    help = 'Adiciona tags de ocorrências padrão ao sistema e desativa tags obsoletas'

    def handle(self, *args, **options):
        # Desativa tags obsoletas/repetidas
        for name in TAGS_TO_DEACTIVATE:
            updated = OccurrenceTag.objects.filter(name__iexact=name.strip()).update(is_active=False)
            if updated:
                self.stdout.write(self.style.WARNING(f'⊘ Tag desativada: {name}'))

        tags_list = [
            # Segurança e acidentes
            {'name': 'Acidente de trabalho', 'color': '#EF4444'},
            {'name': 'Problema de segurança', 'color': '#DC2626'},
            # Clima e paradas
            {'name': 'Condição climática adversa', 'color': '#0EA5E9'},
            {'name': 'Dia parado', 'color': '#6B7280'},
            {'name': 'Paralisação da obra', 'color': '#78716C'},
            {'name': 'Interrupção de serviço', 'color': '#6B7280'},
            # Recursos
            {'name': 'Falta de material', 'color': '#EAB308'},
            {'name': 'Falta de equipamento', 'color': '#F97316'},
            {'name': 'Falta de mão de obra', 'color': '#DC2626'},
            {'name': 'Atraso de fornecedor', 'color': '#F59E0B'},
            # Projeto e liberações
            {'name': 'Projeto não liberado', 'color': '#B45309'},
            {'name': 'Área não liberada', 'color': '#D97706'},
            {'name': 'Falta de liberação', 'color': '#EA580C'},
            {'name': 'Alteração de projeto', 'color': '#F59E0B'},
            {'name': 'Revisão de projeto', 'color': '#3B82F6'},
            # Qualidade e inspeção
            {'name': 'Não conformidade', 'color': '#B91C1C'},
            {'name': 'Inspeção técnica', 'color': '#10B981'},
            {'name': 'Manutenção preventiva', 'color': '#6366F1'},
            # Prazos e produtividade
            {'name': 'Atraso na entrega', 'color': '#F59E0B'},
            {'name': 'Horas improdutivas', 'color': '#8B5CF6'},
            {'name': 'Falta de documentação', 'color': '#64748B'},
        ]

        created_count = 0
        skipped_count = 0

        for tag_data in tags_list:
            tag, created = OccurrenceTag.objects.get_or_create(
                name=tag_data['name'],
                defaults={
                    'color': tag_data['color'],
                    'is_active': True
                }
            )
            if not created and not tag.is_active:
                tag.is_active = True
                tag.color = tag_data['color']
                tag.save()
                self.stdout.write(self.style.SUCCESS(f'✓ Tag reativada: {tag.name}'))
            elif created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Tag criada: {tag.name} ({tag.color})')
                )
            else:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(f'⊘ Tag já existe: {tag.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Processo concluído! {created_count} tags criadas, {skipped_count} já existiam.'
            )
        )
