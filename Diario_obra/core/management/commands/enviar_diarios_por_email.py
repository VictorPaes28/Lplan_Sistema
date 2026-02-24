"""
Comando para enviar os diários de obra por e-mail para os destinatários cadastrados por obra.

Uso:
  python manage.py enviar_diarios_por_email
  python manage.py enviar_diarios_por_email --date=2025-02-18

Agendar (ex.: todo dia às 7h): use o Agendador de Tarefas do Windows ou cron (Linux)
com este comando. Em produção, configure SMTP (EMAIL_HOST, EMAIL_HOST_USER, etc.).
"""
from datetime import date, datetime
from django.core.management.base import BaseCommand

from core.diary_email import send_diary_email_for_date


class Command(BaseCommand):
    help = "Envia por e-mail os diários do dia (ou da data informada) para os e-mails cadastrados em cada obra."

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            default=None,
            help='Data no formato AAAA-MM-DD (padrão: hoje)',
        )

    def handle(self, *args, **options):
        date_str = options.get('date')
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                self.stderr.write(self.style.ERROR(f'Data inválida: {date_str}. Use AAAA-MM-DD.'))
                return
        else:
            target_date = date.today()

        self.stdout.write(f'Enviando diários da data {target_date.strftime("%d/%m/%Y")}...')
        enviados, erros = send_diary_email_for_date(target_date)
        self.stdout.write(self.style.SUCCESS(f'Pronto. E-mails enviados: {enviados}. Erros: {erros}.'))
