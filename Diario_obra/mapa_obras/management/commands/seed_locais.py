from django.core.management.base import BaseCommand
from mapa_obras.models import Obra, LocalObra


class Command(BaseCommand):
    help = 'Cria locais comuns (Bloco A/B, etc) para uma obra'

    def add_arguments(self, parser):
        parser.add_argument('--obra-codigo', type=str, required=True, help='Código da obra no Sienge')
        parser.add_argument('--blocos', type=int, default=0, help='Número de blocos a criar (A, B, C...)')
        parser.add_argument('--pavimentos', type=int, default=0, help='Número de pavimentos por bloco')

    def handle(self, *args, **options):
        obra_codigo = options['obra_codigo']
        num_blocos = options['blocos']
        num_pavimentos = options['pavimentos']
        
        try:
            obra = Obra.objects.get(codigo_sienge=obra_codigo)
        except Obra.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Obra com código {obra_codigo} não encontrada.'))
            return
        
        created = 0
        
        # Criar blocos
        if num_blocos > 0:
            for i in range(num_blocos):
                bloco_nome = chr(65 + i)  # A, B, C...
                bloco, bloco_created = LocalObra.objects.get_or_create(
                    obra=obra,
                    nome=f'Bloco {bloco_nome}',
                    defaults={'tipo': 'BLOCO'}
                )
                if bloco_created:
                    created += 1
                    self.stdout.write(f'Criado: {bloco.nome}')
                
                # Criar pavimentos
                if num_pavimentos > 0:
                    for p in range(1, num_pavimentos + 1):
                        pav, pav_created = LocalObra.objects.get_or_create(
                            obra=obra,
                            nome=f'Pavimento {p}',
                            parent=bloco,
                            defaults={'tipo': 'PAVIMENTO'}
                        )
                        if pav_created:
                            created += 1
                            self.stdout.write(f'  Criado: {pav.nome}')
        
        self.stdout.write(self.style.SUCCESS(f'\nTotal de locais criados: {created}'))
