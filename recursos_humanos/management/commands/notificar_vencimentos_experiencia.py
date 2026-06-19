from django.core.management.base import BaseCommand

from recursos_humanos.services.notificacoes_contrato import processar_notificacoes_contrato


class Command(BaseCommand):
    help = (
        'Envia e-mails automáticos de vencimento de contrato '
        '(experiência, determinado, estágio, PJ e temporário). '
        'Agende no cron diariamente, por exemplo às 8h:\n'
        '  0 8 * * * cd /home/lplan/sistema && python manage.py notificar_vencimentos_experiencia'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula o envio sem mandar e-mails nem gravar registros.',
        )

    def handle(self, *args, **options):
        stats = processar_notificacoes_contrato(dry_run=options['dry_run'])
        modo = ' (dry-run)' if options['dry_run'] else ''
        self.stdout.write(
            f'Prazos analisados: {stats["prazos_analisados"]}{modo}\n'
            f'Notificações enviadas: {stats["notificacoes_enviadas"]}\n'
            f'Ignoradas (já enviadas hoje): {stats["notificacoes_ignoradas"]}\n'
            f'Falhas: {stats["falhas"]}'
        )
