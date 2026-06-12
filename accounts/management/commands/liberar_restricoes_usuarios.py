"""
Concede o grupo «Gestão de Impeditivos» (módulo Restrições) em lote.

Uso:
  python manage.py liberar_restricoes_usuarios --dry-run
  python manage.py liberar_restricoes_usuarios
  python manage.py liberar_restricoes_usuarios --incluir-inativos
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.groups import GRUPOS, ensure_official_groups_exist


class Command(BaseCommand):
    help = (
        "Adiciona o grupo «Gestão de Impeditivos» a todos os usuários que ainda não têm "
        "acesso ao módulo Restrições."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas simula; não grava alterações.",
        )
        parser.add_argument(
            "--incluir-inativos",
            action="store_true",
            help="Inclui usuários com is_active=False.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        incluir_inativos = options["incluir_inativos"]

        ensure_official_groups_exist()
        from django.contrib.auth.models import Group

        grupo = Group.objects.get(name=GRUPOS.GESTAO_IMPEDIMENTOS)

        qs = User.objects.all()
        if not incluir_inativos:
            qs = qs.filter(is_active=True)

        sem_grupo = qs.exclude(groups=grupo).order_by("username")
        total = sem_grupo.count()
        ja_tinham = qs.filter(groups=grupo).count()

        self.stdout.write(
            self.style.MIGRATE_HEADING("\n=== Liberar Restrições (Gestão de Impeditivos) ===\n")
        )
        self.stdout.write(f"Usuários no escopo: {qs.count()}")
        self.stdout.write(f"Já com o grupo: {ja_tinham}")
        self.stdout.write(f"Sem o grupo (serão atualizados): {total}")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("\nNada a fazer — todos já têm acesso."))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] Usuários que receberiam o grupo:"))
            for user in sem_grupo[:20]:
                self.stdout.write(f"  - {user.username} ({user.get_full_name() or user.email})")
            if total > 20:
                self.stdout.write(f"  ... e mais {total - 20}")
            self.stdout.write(self.style.WARNING("\nExecute sem --dry-run para aplicar."))
            return

        with transaction.atomic():
            for user in sem_grupo.iterator():
                user.groups.add(grupo)

        self.stdout.write(
            self.style.SUCCESS(f"\nGrupo concedido a {total} usuário(s).")
        )
