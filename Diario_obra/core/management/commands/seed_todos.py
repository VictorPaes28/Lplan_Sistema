"""
Comando unificado para popular o banco com dados de teste de TODOS os sistemas.
Executa os seeds do GestControll e do Mapa de Suprimentos em sequência.

Uso:
    python manage.py seed_todos              # Cria dados de ambos os sistemas
    python manage.py seed_todos --limpar     # Limpa e recria tudo
    python manage.py seed_todos --gestcontroll   # Apenas GestControll
    python manage.py seed_todos --suprimentos    # Apenas Mapa de Suprimentos
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Popula o banco com dados de teste de todos os sistemas (GestControll + Mapa de Suprimentos)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpar',
            action='store_true',
            help='Limpa dados existentes antes de criar novos'
        )
        parser.add_argument(
            '--gestcontroll',
            action='store_true',
            help='Executa apenas o seed do GestControll'
        )
        parser.add_argument(
            '--suprimentos',
            action='store_true',
            help='Executa apenas o seed do Mapa de Suprimentos'
        )

    def handle(self, *args, **options):
        limpar = options['limpar']
        apenas_gestcontroll = options['gestcontroll']
        apenas_suprimentos = options['suprimentos']

        # Se nenhum flag específico, roda tudo
        rodar_gestcontroll = apenas_gestcontroll or (not apenas_gestcontroll and not apenas_suprimentos)
        rodar_suprimentos = apenas_suprimentos or (not apenas_gestcontroll and not apenas_suprimentos)

        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('=' * 60))
        self.stdout.write(self.style.HTTP_INFO('  LPLAN - Seed de Dados de Teste'))
        self.stdout.write(self.style.HTTP_INFO('=' * 60))
        self.stdout.write('')

        if rodar_gestcontroll:
            self.stdout.write(self.style.HTTP_INFO('--- GestControll (Gestao de Aprovacoes) ---'))
            args_gestcontroll = []
            if limpar:
                args_gestcontroll.append('--limpar')
            call_command('seed_gestcontroll', *args_gestcontroll, stdout=self.stdout)
            self.stdout.write('')

        if rodar_suprimentos:
            self.stdout.write(self.style.HTTP_INFO('--- Mapa de Suprimentos ---'))
            args_suprimentos = []
            if limpar:
                args_suprimentos.append('--limpar')
            call_command('seed_teste', *args_suprimentos, stdout=self.stdout)
            self.stdout.write('')

        self.stdout.write(self.style.HTTP_INFO('=' * 60))
        self.stdout.write(self.style.SUCCESS('Seed completo! Todos os sistemas estao prontos para testes.'))
        self.stdout.write(self.style.HTTP_INFO('=' * 60))
        self.stdout.write('')
        self.stdout.write('Comandos uteis:')
        self.stdout.write('  python manage.py runserver          # Iniciar servidor')
        self.stdout.write('  python manage.py seed_todos --limpar  # Limpar e recriar dados')
        self.stdout.write('')
