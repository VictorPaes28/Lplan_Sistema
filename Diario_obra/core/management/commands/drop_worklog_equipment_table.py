"""
Comando único: remove a tabela core_dailyworklogequipment para permitir
re-executar a migração 0028 (through de equipamentos) após falha parcial.

Uso: python manage.py drop_worklog_equipment_table
Depois: python manage.py migrate core
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Remove a tabela core_dailyworklogequipment (para reaplicar migração 0028)."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            table = connection.ops.quote_name("core_dailyworklogequipment")
            raw_sql = f"DROP TABLE IF EXISTS {table}"
            cursor.execute(raw_sql)
        self.stdout.write(self.style.SUCCESS("Tabela core_dailyworklogequipment removida. Rode: python manage.py migrate core"))
