"""
Diagnóstico de SMTP para isolar o erro 535 ("Incorrect authentication data").

Mostra qual conta (mailbox) cada módulo usa e testa o login real no servidor,
SEM expor a senha. Use em produção:

    python manage.py diagnosticar_smtp

Por que existe: o GestControll envia pelo backend padrão
(EMAIL_HOST_USER/EMAIL_HOST_PASSWORD), enquanto o RDO pode usar uma conta
separada (EMAIL_RDO_HOST_USER/EMAIL_RDO_HOST_PASSWORD). Logo, o 535 pode atingir
apenas a conta do Gest mesmo que o RDO continue funcionando.
"""
import smtplib
import ssl

from django.conf import settings
from django.core.management.base import BaseCommand


def _mascarar(valor):
    if not valor:
        return "(VAZIO)"
    valor = str(valor)
    if "@" in valor:
        local, _, dominio = valor.partition("@")
        visivel = local[:2]
        return f"{visivel}{'*' * max(len(local) - 2, 0)}@{dominio}"
    return valor[:2] + "*" * max(len(valor) - 2, 0)


def _testar_login(host, port, username, password, use_ssl, use_tls, timeout=15):
    """Tenta autenticar no servidor SMTP e devolve (ok, detalhe)."""
    if not host or not username or not password:
        return False, "host/usuário/senha ausentes"
    try:
        if use_ssl:
            contexto = ssl.create_default_context()
            servidor = smtplib.SMTP_SSL(host, port, timeout=timeout, context=contexto)
        else:
            servidor = smtplib.SMTP(host, port, timeout=timeout)
        try:
            servidor.ehlo()
            if use_tls and not use_ssl:
                servidor.starttls(context=ssl.create_default_context())
                servidor.ehlo()
            servidor.login(username, password)
            return True, "AUTH OK"
        finally:
            try:
                servidor.quit()
            except Exception:
                pass
    except smtplib.SMTPAuthenticationError as exc:
        return False, f"SMTPAuthenticationError: {exc}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


class Command(BaseCommand):
    help = "Diagnostica autenticação SMTP do GestControll e do RDO (erro 535)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--testar-rdo",
            action="store_true",
            help="Também testa o login da conta dedicada do RDO (se configurada).",
        )

    def handle(self, *args, **options):
        backend = getattr(settings, "EMAIL_BACKEND", "")
        host = getattr(settings, "EMAIL_HOST", "")
        port = getattr(settings, "EMAIL_PORT", "")
        use_ssl = getattr(settings, "EMAIL_USE_SSL", False)
        use_tls = getattr(settings, "EMAIL_USE_TLS", False)
        user = getattr(settings, "EMAIL_HOST_USER", "")
        senha = getattr(settings, "EMAIL_HOST_PASSWORD", "")
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "")

        self.stdout.write(self.style.MIGRATE_HEADING("== Configuração efetiva (processo em execução) =="))
        self.stdout.write(f"  EMAIL_BACKEND      : {backend}")
        self.stdout.write(f"  EMAIL_HOST         : {host}")
        self.stdout.write(f"  EMAIL_PORT         : {port}")
        self.stdout.write(f"  EMAIL_USE_SSL      : {use_ssl}")
        self.stdout.write(f"  EMAIL_USE_TLS      : {use_tls}")
        self.stdout.write(f"  EMAIL_HOST_USER    : {_mascarar(user)}  (conta usada pelo GestControll)")
        self.stdout.write(f"  EMAIL_HOST_PASSWORD: {'definida' if senha else '(VAZIA)'}  (len={len(senha) if senha else 0})")
        self.stdout.write(f"  DEFAULT_FROM_EMAIL : {_mascarar(from_email)}")

        rdo_from = (getattr(settings, "EMAIL_RDO_FROM", "") or "").strip()
        rdo_user = (getattr(settings, "EMAIL_RDO_HOST_USER", "") or "").strip()
        rdo_pass = getattr(settings, "EMAIL_RDO_HOST_PASSWORD", "")
        rdo_ativo = bool(rdo_from and rdo_user and rdo_pass)
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("== Conta dedicada do RDO =="))
        self.stdout.write(f"  RDO dedicado ativo : {rdo_ativo}")
        self.stdout.write(f"  EMAIL_RDO_HOST_USER: {_mascarar(rdo_user)}")
        if rdo_ativo:
            self.stdout.write(self.style.WARNING(
                "  -> RDO autentica com OUTRA conta. Por isso o RDO pode funcionar "
                "mesmo com o GestControll falhando no 535."
            ))
        else:
            self.stdout.write(
                "  -> RDO usa a MESMA conta padrão do GestControll (sem conta dedicada)."
            )

        if "smtp" not in backend.lower():
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                f"EMAIL_BACKEND não é SMTP ({backend}). Em produção deve ser o backend SMTP "
                "para o teste de login fazer sentido."
            ))
            return

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("== Teste de login SMTP (GestControll / conta padrão) =="))
        ok, detalhe = _testar_login(host, port, user, senha, use_ssl, use_tls)
        if ok:
            self.stdout.write(self.style.SUCCESS(f"  GestControll: {detalhe}"))
        else:
            self.stdout.write(self.style.ERROR(f"  GestControll: FALHOU -> {detalhe}"))
            self.stdout.write(
                "  Se aparecer 535/Incorrect authentication data: a conta padrão "
                f"({_mascarar(user)}) está sendo recusada pelo servidor (senha/quota/bloqueio)."
            )

        if options.get("testar_rdo") and rdo_ativo:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("== Teste de login SMTP (RDO dedicado) =="))
            rdo_host = getattr(settings, "EMAIL_RDO_HOST", None) or host
            rdo_port = getattr(settings, "EMAIL_RDO_PORT", None) or port
            rdo_ssl = getattr(settings, "EMAIL_RDO_USE_SSL", use_ssl)
            rdo_tls = getattr(settings, "EMAIL_RDO_USE_TLS", use_tls)
            ok_rdo, detalhe_rdo = _testar_login(rdo_host, rdo_port, rdo_user, rdo_pass, rdo_ssl, rdo_tls)
            if ok_rdo:
                self.stdout.write(self.style.SUCCESS(f"  RDO: {detalhe_rdo}"))
            else:
                self.stdout.write(self.style.ERROR(f"  RDO: FALHOU -> {detalhe_rdo}"))

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("== Conclusão =="))
        if not ok:
            self.stdout.write(
                "O erro está na AUTENTICAÇÃO da conta padrão usada pelo GestControll, "
                "no momento do login SMTP (email.send()). Não é o botão nem o PDF: é a "
                f"credencial da conta {_mascarar(user)} que o servidor está recusando."
            )
        else:
            self.stdout.write(
                "Login da conta padrão OK agora. Se houve 535 antes, foi bloqueio/quota "
                "temporária do servidor para essa conta (recupera sozinho) ou processo "
                "rodando com variáveis antigas (precisa reiniciar o app)."
            )
