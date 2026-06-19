"""Limpa simulações do RH e repopula dados de demonstração alinhados ao fluxo atual."""
from django.core.management.base import BaseCommand

from recursos_humanos.seed_demo_rh import limpar_dados_operacionais_rh, popular_demo_rh


class Command(BaseCommand):
    help = 'Remove colaboradores de simulação e recria o quadro de demonstração do RH.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--somente-limpar',
            action='store_true',
            help='Apenas remove colaboradores/contratos/prazos, sem recriar dados.',
        )

    def handle(self, *args, **options):
        if options['somente_limpar']:
            removidos = limpar_dados_operacionais_rh()
            self.stdout.write(self.style.WARNING(
                f'Removidos: {removidos["colaboradores"]} colaborador(es), '
                f'{removidos["contratos"]} contrato(s), {removidos["prazos"]} prazo(s).'
            ))
            return

        resultado = popular_demo_rh()
        self.stdout.write(self.style.SUCCESS(
            f'RH repopulado: {resultado["colaboradores"]} colaboradores, '
            f'{resultado["cargos"]} cargos, {resultado["tipos_documento"]} tipos de documento ativos.'
        ))
        self.stdout.write('Colaboradores:')
        for nome in resultado['nomes']:
            self.stdout.write(f'  • {nome}')
