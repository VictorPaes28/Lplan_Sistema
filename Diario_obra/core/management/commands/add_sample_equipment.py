"""
Management command para adicionar equipamentos de exemplo ao sistema.
"""
from django.core.management.base import BaseCommand
from core.models import Equipment


class Command(BaseCommand):
    help = 'Adiciona equipamentos de exemplo ao sistema'

    def handle(self, *args, **options):
        equipment_list = [
            {'name': 'Escavadeira Hidráulica', 'code': 'EQ001', 'equipment_type': 'Escavadeira'},
            {'name': 'Betoneira 400L', 'code': 'EQ002', 'equipment_type': 'Betoneira'},
            {'name': 'Guindaste 30T', 'code': 'EQ003', 'equipment_type': 'Guindaste'},
            {'name': 'Rolo Compactador', 'code': 'EQ004', 'equipment_type': 'Compactador'},
            {'name': 'Caminhão Munck', 'code': 'EQ005', 'equipment_type': 'Caminhão'},
            {'name': 'Retroescavadeira', 'code': 'EQ006', 'equipment_type': 'Escavadeira'},
            {'name': 'Caminhão Basculante', 'code': 'EQ007', 'equipment_type': 'Caminhão'},
            {'name': 'Gerador 50KVA', 'code': 'EQ008', 'equipment_type': 'Gerador'},
            {'name': 'Compressor de Ar', 'code': 'EQ009', 'equipment_type': 'Compressor'},
            {'name': 'Furadeira de Impacto', 'code': 'EQ010', 'equipment_type': 'Ferramenta'},
            {'name': 'Soldadora', 'code': 'EQ011', 'equipment_type': 'Soldadora'},
            {'name': 'Cortadora de Piso', 'code': 'EQ012', 'equipment_type': 'Ferramenta'},
            {'name': 'Bomba de Concreto', 'code': 'EQ013', 'equipment_type': 'Bomba'},
            {'name': 'Andaime Metálico', 'code': 'EQ014', 'equipment_type': 'Andaime'},
            {'name': 'Cimbramento', 'code': 'EQ015', 'equipment_type': 'Cimbramento'},
        ]

        created_count = 0
        skipped_count = 0

        for eq_data in equipment_list:
            equipment, created = Equipment.objects.get_or_create(
                code=eq_data['code'],
                defaults={
                    'name': eq_data['name'],
                    'equipment_type': eq_data['equipment_type'],
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Equipamento criado: {equipment.name} ({equipment.code})')
                )
            else:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(f'⊘ Equipamento já existe: {equipment.name} ({equipment.code})')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Processo concluído! {created_count} equipamentos criados, {skipped_count} já existiam.'
            )
        )

