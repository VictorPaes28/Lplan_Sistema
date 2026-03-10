"""
Envio de diários de obra por e-mail (envio diário para os e-mails cadastrados por obra).
Envia o PDF do diário em anexo; se a geração do PDF falhar, envia apenas o link.
Usado pelo comando enviar_diarios_por_email e opcionalmente por tarefa Celery.

Se EMAIL_RDO_FROM e EMAIL_RDO_HOST_USER estiverem configurados, os e-mails do RDO
são enviados por essa conta (ex.: rdo@lplan.com.br); caso contrário usa DEFAULT_FROM_EMAIL.
"""
import logging
from datetime import date
from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.urls import reverse

logger = logging.getLogger(__name__)


def _get_rdo_connection_and_from():
    """
    Retorna (connection, from_email) para envio de e-mails do RDO.
    Se EMAIL_RDO_FROM e EMAIL_RDO_HOST_USER estiverem definidos, usa conexão SMTP
    específica do RDO; senão retorna (None, DEFAULT_FROM_EMAIL) para usar o backend padrão.
    """
    rdo_from = getattr(settings, 'EMAIL_RDO_FROM', '').strip()
    rdo_user = getattr(settings, 'EMAIL_RDO_HOST_USER', '').strip()
    rdo_pass = getattr(settings, 'EMAIL_RDO_HOST_PASSWORD', '')
    if rdo_from and rdo_user and rdo_pass:
        conn = get_connection(
            backend=getattr(settings, 'EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend'),
            host=getattr(settings, 'EMAIL_RDO_HOST', None) or getattr(settings, 'EMAIL_HOST', 'localhost'),
            port=getattr(settings, 'EMAIL_RDO_PORT', None) or getattr(settings, 'EMAIL_PORT', 25),
            username=rdo_user,
            password=rdo_pass,
            use_tls=getattr(settings, 'EMAIL_RDO_USE_TLS', getattr(settings, 'EMAIL_USE_TLS', False)),
            use_ssl=getattr(settings, 'EMAIL_RDO_USE_SSL', getattr(settings, 'EMAIL_USE_SSL', False)),
            fail_silently=False,
        )
        return conn, rdo_from
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'sistema@lplan.com.br')
    return None, from_email


def get_diary_url(diary):
    """Retorna a URL absoluta para visualizar o diário."""
    path = reverse('diary-detail', kwargs={'pk': diary.pk})
    return f"{getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')}{path}"


def get_client_diary_url(diary):
    """Retorna a URL absoluta para o dono da obra visualizar o diário (portal cliente)."""
    path = reverse('client-diary-detail', kwargs={'pk': diary.pk})
    return f"{getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')}{path}"


def send_diary_to_owners(diary):
    """
    Envia e-mail para cada dono da obra com link direto para a página do diário (portal cliente).
    Chamado quando o diário é salvo como "Salvar diário" (status APROVADO).
    """
    from core.models import ProjectOwner

    owners = ProjectOwner.objects.filter(project=diary.project).select_related('user')
    if not owners:
        return

    link = get_client_diary_url(diary)
    project = diary.project
    target_date = diary.date
    subject = f"Diário de Obra - {project.name} - {target_date.strftime('%d/%m/%Y')}"
    body = f"""Prezado(a) senhor(a),

Informamos que o diário de obra referente ao dia {target_date.strftime('%d/%m/%Y')} da obra {project.name} ({project.code}) foi aprovado e está disponível para visualização.

Para acessar o documento e enviar comentários (prazo de 24 horas a partir do recebimento deste e-mail), utilize o link abaixo:

{link}

Atenciosamente,

LPLAN - Diário de Obra
Mensagem automática. Não responda a este e-mail.
"""
    connection, from_email = _get_rdo_connection_and_from()
    try:
        for po in owners:
            email_addr = po.user.email
            if not email_addr:
                continue
            try:
                EmailMessage(
                    subject=subject,
                    body=body,
                    from_email=from_email,
                    to=[email_addr],
                    connection=connection,
                ).send(fail_silently=False)
                logger.info("Enviado diário %s ao dono da obra %s.", diary.pk, po.user.username)
            except Exception as e:
                logger.exception("Erro ao enviar diário ao dono %s: %s", po.user.username, e)
    finally:
        if connection:
            connection.close()


def _generate_diary_pdf(diary):
    """
    Gera o PDF do diário em memória. Retorna BytesIO ou None se falhar.
    """
    try:
        from core.utils.pdf_generator import PDFGenerator
        pdf_bytes = PDFGenerator.generate_diary_pdf(diary.pk)
        if pdf_bytes and pdf_bytes.getvalue():
            return pdf_bytes
    except Exception as e:
        logger.warning("Não foi possível gerar PDF do diário %s: %s. E-mail será enviado apenas com o link.", diary.pk, e)
    return None


def send_diary_email_for_date(target_date=None):
    """
    Para cada obra que tem e-mails cadastrados, verifica se existe diário na data,
    gera o PDF do diário e envia um e-mail com o PDF em anexo (e o link no corpo).
    Se a geração do PDF falhar, envia o e-mail apenas com o link.

    target_date: date ou None (usa hoje).
    Retorna: (enviados, erros) contagem.
    """
    from core.models import Project, ConstructionDiary

    if target_date is None:
        target_date = date.today()

    enviados = 0
    erros = 0

    projects_with_recipients = Project.objects.filter(
        diary_recipients__isnull=False,
        is_active=True,
    ).distinct()

    for project in projects_with_recipients:
        recipients = list(project.diary_recipients.values_list('email', flat=True))
        if not recipients:
            continue

        diary = ConstructionDiary.objects.filter(
            project=project,
            date=target_date,
        ).first()

        if not diary:
            logger.debug("Obra %s: sem diário na data %s, nada a enviar.", project.code, target_date)
            continue

        link = get_diary_url(diary)
        subject = f"Diário de Obra - {project.name} - {target_date.strftime('%d/%m/%Y')}"
        pdf_bytes = _generate_diary_pdf(diary)

        if pdf_bytes:
            body = f"""Prezado(a) senhor(a),

Segue em anexo o diário de obra referente ao dia {target_date.strftime('%d/%m/%Y')} da obra {project.name} ({project.code}).

Para visualizar no sistema: {link}

Atenciosamente,

LPLAN - Diário de Obra
Mensagem automática. Não responda a este e-mail.
"""
        else:
            body = f"""Prezado(a) senhor(a),

O diário de obra referente ao dia {target_date.strftime('%d/%m/%Y')} da obra {project.name} ({project.code}) está disponível para visualização.

Acesse o sistema (faça login se necessário): {link}

Atenciosamente,

LPLAN - Diário de Obra
Mensagem automática. Não responda a este e-mail.
"""

        try:
            connection, from_email = _get_rdo_connection_and_from()
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=from_email,
                to=recipients,
                connection=connection,
            )
            if pdf_bytes:
                filename = f"Diario_{project.code}_{target_date.strftime('%Y-%m-%d')}.pdf"
                email.attach(filename, pdf_bytes.getvalue(), 'application/pdf')
            email.send(fail_silently=False)
            if connection:
                connection.close()
            enviados += len(recipients)
            logger.info(
                "Enviado diário obra %s (%s) para %d e-mail(s)%s.",
                project.code, target_date, len(recipients),
                " (com PDF em anexo)" if pdf_bytes else " (apenas link)",
            )
        except Exception as e:
            erros += len(recipients)
            logger.exception("Erro ao enviar diário obra %s para %s: %s", project.code, recipients, e)

    return enviados, erros
