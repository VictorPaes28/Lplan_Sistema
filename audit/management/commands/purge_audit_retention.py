from django.core.management.base import BaseCommand

from audit.retention import purge_audit_events_older_than, purge_user_login_logs_older_than


class Command(BaseCommand):
    help = (
        'Remove AuditEvent e UserLoginLog mais antigos que a política (AuditRetentionPolicy) '
        'ou que os dias indicados. Use --dry-run para apenas contar.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Só mostra quantos registos seriam apagados.',
        )
        parser.add_argument(
            '--audit-days',
            type=int,
            default=None,
            help='Ignora a política e usa N dias para auditoria.',
        )
        parser.add_argument(
            '--login-days',
            type=int,
            default=None,
            help='Ignora a política e usa N dias para logins.',
        )
        parser.add_argument(
            '--only-audit',
            action='store_true',
            help='Só expurga AuditEvent.',
        )
        parser.add_argument(
            '--only-login',
            action='store_true',
            help='Só expurga UserLoginLog.',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        only_audit = options['only_audit']
        only_login = options['only_login']
        if only_audit and only_login:
            self.stderr.write('Use apenas um de --only-audit / --only-login.')
            return

        if not only_login:
            n = purge_audit_events_older_than(days=options['audit_days'], dry_run=dry)
            self.stdout.write(
                self.style.WARNING(f"AuditEvent: {n} registo(s) {'(simulação)' if dry else 'apagado(s)'}."),
            )
        if not only_audit:
            n2 = purge_user_login_logs_older_than(days=options['login_days'], dry_run=dry)
            self.stdout.write(
                self.style.WARNING(f"UserLoginLog: {n2} registo(s) {'(simulação)' if dry else 'apagado(s)'}."),
            )
