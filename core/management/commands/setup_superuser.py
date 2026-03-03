"""
Comando Django para criar superuser de forma interativa ou não-interativa.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import getpass


class Command(BaseCommand):
    help = 'Cria um superuser para o sistema'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Username do superuser',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email do superuser',
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Senha do superuser (não recomendado em produção)',
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            help='Modo não-interativo (requer --username, --email e --password)',
        )

    def handle(self, *args, **options):
        username = options.get('username')
        email = options.get('email')
        password = options.get('password')
        noinput = options.get('noinput', False)

        # Verifica se já existe um superuser
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                self.style.WARNING('Já existe um superuser no sistema.')
            )
            if not noinput:
                response = input('Deseja criar outro? (s/N): ')
                if response.lower() != 's':
                    self.stdout.write(self.style.SUCCESS('Operação cancelada.'))
                    return

        # Modo interativo
        if not noinput:
            self.stdout.write(self.style.SUCCESS('Criando superuser...'))
            
            if not username:
                username = input('Username: ')
            
            if not email:
                email = input('Email: ')
            
            if not password:
                password = getpass.getpass('Senha: ')
                password_confirm = getpass.getpass('Confirme a senha: ')
                
                if password != password_confirm:
                    self.stdout.write(
                        self.style.ERROR('As senhas não coincidem!')
                    )
                    return
        else:
            # Modo não-interativo
            if not username or not email or not password:
                self.stdout.write(
                    self.style.ERROR(
                        'Modo não-interativo requer --username, --email e --password'
                    )
                )
                return

        # Verifica se o username já existe
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.ERROR(f'Username "{username}" já existe!')
            )
            return

        # Cria o superuser
        try:
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Superuser "{username}" criado com sucesso!'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Erro ao criar superuser: {e}')
            )

