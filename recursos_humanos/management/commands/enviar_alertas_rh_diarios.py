from django.core.management.base import BaseCommand

from recursos_humanos.services.alertas_email import enviar_emails_alertas_diarios
from recursos_humanos.services.alerts import gerar_alertas


class Command(BaseCommand):
    help = (
        'Envia o resumo diário de alertas RH (documentos e prazos de contrato). '
        'Período de experiência CLT usa o comando notificar_vencimentos_experiencia. '
        'Agende no cron, por exemplo às 7h:\n'
        '  0 7 * * * cd /home/lplan/sistema && python manage.py enviar_alertas_rh_diarios'
    )

    def handle(self, *args, **options):
        alertas = gerar_alertas()
        enviados = enviar_emails_alertas_diarios(alertas)
        self.stdout.write(
            f'Alertas analisados: {len(alertas)}\n'
            f'E-mails enviados: {enviados}'
        )
