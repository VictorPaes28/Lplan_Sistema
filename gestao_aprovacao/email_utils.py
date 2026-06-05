"""
Utilitários para envio de e-mails de notificação.
"""
import logging
import threading
import os
import time
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils.html import strip_tags
from django.utils import timezone
from django.urls import reverse

logger = logging.getLogger(__name__)

# Fallback quando o banco ainda não tem registros (ex.: antes da migração) ou tabela vazia.
_APROVACAO_DESTINATARIOS_PADRAO = (
    "luiz.henrique@lplan.com.br",
    "luizdomingos@lplan.com.br",
)


def _filtrar_destinatarios_router(destinatarios, tipo_codigo, contexto=None):
    """Aplica central de comunicação; em falha mantém lista original."""
    try:
        from core.comunicacao_router import ComunicacaoPreferenciasService

        return ComunicacaoPreferenciasService().filtrar_destinatarios_email(
            destinatarios,
            tipo_codigo,
            contexto=contexto or {},
        )
    except Exception as exc:
        logger.warning(
            'Router de comunicação indisponível para %s: %s — mantém destinatários.',
            tipo_codigo,
            exc,
        )
        return _normalizar_destinatarios(destinatarios)


def _normalizar_destinatarios(destinatarios):
    """Remove vazios/duplicados e normaliza e-mails mantendo ordem."""
    if not destinatarios:
        return []
    normalizados = []
    seen = set()
    for email in destinatarios:
        e = (email or "").strip().lower()
        if not e or e in seen:
            continue
        seen.add(e)
        normalizados.append(e)
    return normalizados


def _build_workorder_detail_url(workorder):
    base = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
    path = reverse('gestao:detail_workorder', args=[workorder.pk])
    if base:
        return f'{base}{path}'
    return path


def _build_email_logo_url():
    """
    Resolve URL absoluta da logo da LPLAN para uso no cabeçalho dos e-mails.
    Prioriza os mesmos arquivos usados nos PDFs.
    """
    base = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
    static_candidates = (
        '/static/core/images/lpla-logo-pdf-transparent.png',
        '/static/core/images/lpla-logo-pdf.png',
        '/static/core/images/lplan-logo2.png',
        '/static/images/lplan-logo.png',
    )
    if base:
        return f'{base}{static_candidates[0]}'
    return static_candidates[0]


def _get_destinatarios_fixos_aprovacao_para_obra(obra):
    """
    Destinatários cadastrados que devem receber cópia do e-mail de pedido aprovado
    para a obra indicada.

    Regra: se o cadastro não tiver obras selecionadas, vale para todas; se tiver,
    só entra quando ``obra`` está na lista.

    Se não houver nenhum registro ativo no banco, mantém o fallback (.env / lista mínima).
    """
    try:
        from django.db.models import Count, Q
        from .models import AprovacaoEmailDestinatario

        base = AprovacaoEmailDestinatario.objects.filter(ativo=True)
        if not base.exists():
            configured = getattr(settings, "EMAIL_APROVACAO_DESTINATARIOS_FIXOS", None)
            if configured:
                return _normalizar_destinatarios(configured)
            return list(_APROVACAO_DESTINATARIOS_PADRAO)

        qs = (
            base.annotate(_nobras=Count('obras', distinct=True))
            .filter(Q(_nobras=0) | Q(obras=obra))
            .order_by('ordem', 'email')
        )
        return _normalizar_destinatarios(list(qs.values_list('email', flat=True)))
    except Exception as e:
        logger.warning("Destinatários de aprovação no banco indisponíveis: %s", e)

    configured = getattr(settings, "EMAIL_APROVACAO_DESTINATARIOS_FIXOS", None)
    if configured:
        return _normalizar_destinatarios(configured)
    return list(_APROVACAO_DESTINATARIOS_PADRAO)


def _criar_log_email(tipo_email, workorder, destinatarios, assunto):
    """
    Cria um registro de log de email.
    Se falhar, retorna None mas não impede o envio do email.
    """
    try:
        from .models import EmailLog
        
        return EmailLog.objects.create(
            tipo_email=tipo_email,
            work_order=workorder,
            destinatarios=', '.join(destinatarios) if isinstance(destinatarios, list) else destinatarios,
            assunto=assunto,
            status='pendente'
        )
    except Exception as e:
        # Se falhar ao criar log, apenas registra no logger mas não impede o envio
        logger.warning(f"Erro ao criar log de email (email ainda será enviado): {e}")
        return None


def _enviar_email_com_retry(email_obj, email_log, max_tentativas=3, delay=2):
    """
    Envia email com retry automático em caso de falha.
    
    Args:
        email_obj: Objeto EmailMessage ou EmailMultiAlternatives
        email_log: Instância de EmailLog para registrar (pode ser None)
        max_tentativas: Número máximo de tentativas (padrão: 3)
        delay: Delay entre tentativas em segundos (padrão: 2)
    
    Returns:
        bool: True se enviado com sucesso, False caso contrário
    """
    ultimo_erro = None
    
    for tentativa in range(1, max_tentativas + 1):
        try:
            email_obj.send(fail_silently=False)
            # Atualizar log se existir
            if email_log:
                try:
                    email_log.marcar_como_enviado()
                    logger.info(f"Email enviado com sucesso (tentativa {tentativa}/{max_tentativas}) - Log ID: {email_log.pk}")
                except Exception as log_error:
                    logger.warning(f"Email enviado mas erro ao atualizar log: {log_error}")
            else:
                logger.info(f"Email enviado com sucesso (tentativa {tentativa}/{max_tentativas}) - Sem log")
            return True
        except Exception as e:
            ultimo_erro = e
            # Atualizar log se existir
            if email_log:
                try:
                    email_log.marcar_como_falhou(str(e))
                    logger.warning(
                        f"Tentativa {tentativa}/{max_tentativas} falhou para email log {email_log.pk}: {e}"
                    )
                except Exception as log_error:
                    logger.warning(f"Erro ao atualizar log de falha: {log_error}")
            else:
                logger.warning(f"Tentativa {tentativa}/{max_tentativas} falhou (sem log): {e}")
            
            # Se não for a última tentativa, aguarda antes de tentar novamente
            if tentativa < max_tentativas:
                time.sleep(delay)
    
    # Se chegou aqui, todas as tentativas falharam
    log_id = email_log.pk if email_log else "N/A"
    logger.error(
        f"Falha ao enviar email após {max_tentativas} tentativas - Log ID: {log_id} - Erro: {ultimo_erro}"
    )
    return False


def _gerar_html_email(titulo, conteudo, workorder=None, url_detalhes=None):
    """
    Gera HTML limpo e profissional para emails (sem gradientes, visual neutro).
    """
    logo_url = _build_email_logo_url()
    current_year = timezone.now().year
    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                font-size: 15px;
                line-height: 1.5;
                color: #374151;
                max-width: 560px;
                margin: 0 auto;
                padding: 24px 20px;
                background-color: #f9fafb;
            }}
            .email-container {{
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
            }}
            .email-header {{
                padding: 20px 24px;
                border-bottom: 1px solid #e5e7eb;
                background: #ffffff;
            }}
            .brand-wrap {{
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 10px;
            }}
            .brand-logo {{
                max-width: 140px;
                width: 100%;
                height: auto;
                display: block;
            }}
            .brand-sub {{
                font-size: 11px;
                color: #64748b;
                letter-spacing: .08em;
                text-transform: uppercase;
            }}
            .email-header-meta {{
                margin: 2px 0 0 0;
                font-size: 12px;
                color: #64748b;
            }}
            .email-header h1 {{
                margin: 14px 0 0 0;
                font-size: 18px;
                font-weight: 600;
                color: #111827;
            }}
            .email-body {{
                padding: 24px;
            }}
            .email-body p {{
                margin: 0 0 16px 0;
            }}
            .info-box {{
                background: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 4px;
                padding: 16px 20px;
                margin: 20px 0;
            }}
            .info-row {{
                margin: 0;
                padding: 6px 0;
                border-bottom: 1px solid #f3f4f6;
                font-size: 14px;
            }}
            .info-row:last-child {{
                border-bottom: none;
            }}
            .info-label {{
                font-weight: 500;
                color: #6b7280;
                display: inline-block;
                min-width: 120px;
            }}
            .info-value {{
                color: #111827;
            }}
            .btn-wrap {{
                margin: 24px 0 0 0;
            }}
            .btn {{
                display: inline-block;
                padding: 10px 18px;
                background: #0e6da8;
                color: #ffffff !important;
                text-decoration: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }}
            .email-footer {{
                padding: 16px 24px;
                border-top: 1px solid #f3f4f6;
                font-size: 12px;
                color: #9ca3af;
                background: #f8fafc;
            }}
            .email-footer p {{
                margin: 0 0 4px 0;
            }}
            .comentario-box {{
                background: #fefce8;
                border: 1px solid #fef08a;
                border-radius: 4px;
                padding: 12px 16px;
                margin: 16px 0;
                font-size: 14px;
            }}
            .comentario-box strong {{
                color: #854d0e;
            }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="email-header">
                <div class="brand-wrap">
                    <img class="brand-logo" src="{logo_url}" alt="LPLAN">
                    <span class="brand-sub">Engenharia integrada</span>
                </div>
                <p class="email-header-meta">GestControll · Comunicação automática</p>
                <h1>{titulo}</h1>
            </div>
            <div class="email-body">
                {conteudo}
    """
    if workorder:
        html += f"""
                <div class="info-box">
                    <div class="info-row">
                        <span class="info-label">Pedido</span>
                        <span class="info-value"><strong>{workorder.codigo}</strong></span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Obra</span>
                        <span class="info-value">{workorder.obra.nome} ({workorder.obra.codigo})</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Credor</span>
                        <span class="info-value">{workorder.nome_credor}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Tipo</span>
                        <span class="info-value">{workorder.get_tipo_solicitacao_display()}</span>
                    </div>
        """
        if hasattr(workorder, 'criado_por') and workorder.criado_por:
            html += f"""
                    <div class="info-row">
                        <span class="info-label">Solicitante</span>
                        <span class="info-value">{workorder.criado_por.get_full_name() or workorder.criado_por.username}</span>
                    </div>
            """
        html += """
                </div>
        """
    if url_detalhes:
        html += f"""
                <div class="btn-wrap">
                    <a href="{url_detalhes}" class="btn">Ver detalhes no sistema</a>
                </div>
        """
    html += """
            </div>
            <div class="email-footer">
                <p>GestControll · Mensagem automática. Não responda a este e-mail.</p>
                <p>© {current_year} LPLAN Engenharia Integrada.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html


def build_email_credenciais_payload(email_destino, username, senha_plana, nome_completo=None, site_url=None):
    """Monta payload (destino/assunto/texto/html) do e-mail de credenciais."""
    url = site_url or getattr(settings, 'SITE_URL', None) or 'http://sistema.lplan.com.br'
    nome = (nome_completo or username).strip()
    assunto = 'Acesso ao sistema LPLAN - seus dados de login'
    mensagem_texto = f"""Olá, {nome},

Seu acesso ao sistema da LPLAN já está liberado. Abaixo estão as informações para o seu primeiro login:



Link de acesso: {url}

Usuário: {username}

Senha temporária: {senha_plana}


Importante: Por questões de segurança, recomendamos que você altere sua senha logo no primeiro acesso através do menu de Perfil ou Configurações.

Se encontrar qualquer dificuldade técnica ou tiver dúvidas sobre o uso das ferramentas, pode entrar em contato diretamente com o suporte interno.

Bom trabalho,

LPLAN
"""
    conteudo_html = f"""
                <p>Olá, <strong>{nome}</strong>.</p>
                <p>Seu acesso ao sistema da LPLAN já está liberado. Use os dados abaixo para o primeiro login:</p>
                <div class="info-box">
                    <div class="info-row">
                        <span class="info-label">Link de acesso</span>
                        <span class="info-value">{url}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Usuário</span>
                        <span class="info-value"><strong>{username}</strong></span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Senha temporária</span>
                        <span class="info-value"><strong>{senha_plana}</strong></span>
                    </div>
                </div>
                <p>Por segurança, altere sua senha logo no primeiro acesso, em <strong>Perfil</strong> ou <strong>Configurações</strong>.</p>
                <p>Se precisar de apoio, entre em contato com o suporte interno.</p>
    """
    html_content = _gerar_html_email(
        "Acesso liberado ao sistema",
        conteudo_html,
        workorder=None,
        url_detalhes=url,
    )
    return {
        'destinatarios': [email_destino.strip()],
        'assunto': assunto,
        'mensagem_texto': mensagem_texto,
        'html_content': html_content,
    }


def build_email_novo_pedido_payload(workorder):
    """Monta payload (destinos/assunto/texto/html) do e-mail de novo pedido."""
    from .models import WorkOrderPermission
    from core.comunicacao_constants import TIPO_GESTCONTROLL_NOVO_PEDIDO

    obra = workorder.obra
    permissoes_aprovadores = WorkOrderPermission.objects.filter(
        obra=obra,
        tipo_permissao='aprovador',
        ativo=True,
    ).select_related('usuario')
    aprovadores = [p.usuario for p in permissoes_aprovadores if p.usuario.is_active]
    destinatarios = [a.email for a in aprovadores if a.email]
    if obra.email_obra:
        destinatarios.append(obra.email_obra)
    destinatarios = _filtrar_destinatarios_router(
        destinatarios,
        TIPO_GESTCONTROLL_NOVO_PEDIDO,
        contexto={
            'modulo': 'gestcontroll',
            'objeto_tipo': 'work_order',
            'objeto_id': workorder.pk,
            'origem': 'novo_pedido',
        },
    )

    assunto = f'Novo Pedido Pendente: {workorder.codigo} - {obra.nome}'
    url_detalhes = _build_workorder_detail_url(workorder)
    mensagem_texto = f"""
Um novo pedido de obra foi criado e está aguardando sua aprovação.

Pedido: {workorder.codigo}
Obra: {obra.nome} ({obra.codigo})
Credor: {workorder.nome_credor}
Tipo: {workorder.get_tipo_solicitacao_display()}
Solicitante: {workorder.criado_por.get_full_name() or workorder.criado_por.username if workorder.criado_por else '—'}
E-mail do Solicitante: {workorder.criado_por.email if workorder.criado_por else '—'}
Data de Envio: {workorder.data_envio.strftime('%d/%m/%Y %H:%M') if workorder.data_envio else 'N/A'}

Observações:
{workorder.observacoes or 'Nenhuma observação'}

Acesse o sistema para aprovar ou reprovar este pedido:
{url_detalhes}

Atenciosamente,

GestControll
Mensagem automática. Não responda a este e-mail.
"""
    observacoes_html = (
        f"<p><strong>Observações:</strong><br>{workorder.observacoes or 'Nenhuma observação'}</p>"
        if workorder.observacoes else ""
    )
    conteudo_html = f"""
                <p>Um novo pedido de obra foi criado e está <strong>aguardando sua aprovação</strong>.</p>
                {observacoes_html}
                <div class="info-row">
                    <span class="info-label">Data de Envio:</span>
                    <span class="info-value">{workorder.data_envio.strftime('%d/%m/%Y %H:%M') if workorder.data_envio else 'N/A'}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">E-mail do Solicitante:</span>
                    <span class="info-value">{workorder.criado_por.email if workorder.criado_por else '—'}</span>
                </div>
    """
    html_content = _gerar_html_email("Novo Pedido Pendente", conteudo_html, workorder, url_detalhes)
    return {
        'destinatarios': destinatarios,
        'assunto': assunto,
        'mensagem_texto': mensagem_texto,
        'html_content': html_content,
    }


def enviar_email_credenciais_novo_usuario(email_destino, username, senha_plana, nome_completo=None, site_url=None):
    """
    Envia e-mail ao novo usuário com login e senha de acesso ao sistema.
    Chamado ao criar usuário pelo painel (create_user).
    """
    if not email_destino or not email_destino.strip():
        return False
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        logger.warning(
            "E-mail não configurado. Credenciais do novo usuário não enviadas. "
            "Configure EMAIL_HOST_USER e EMAIL_HOST_PASSWORD."
        )
        return False
    try:
        from django.contrib.auth import get_user_model
        from core.comunicacao_constants import TIPO_CADASTRO_CREDENCIAIS
        from core.comunicacao_router import ComunicacaoPreferenciasService

        User = get_user_model()
        usuario_destino = User.objects.filter(email__iexact=(email_destino or '').strip(), is_active=True).first()
        decisao = ComunicacaoPreferenciasService().pode_enviar_email(
            email_destino,
            TIPO_CADASTRO_CREDENCIAIS,
            usuario=usuario_destino,
            contexto={
                'modulo': 'cadastro',
                'objeto_tipo': 'usuario',
                'objeto_id': username,
                'origem': 'credenciais_novo_usuario',
            },
        )
        if not decisao.enviar:
            logger.info(
                "Envio de credenciais bloqueado por preferência (%s). Destino: %s",
                decisao.motivo,
                email_destino,
            )
            return False
    except Exception as exc:
        logger.warning(
            'Router de comunicação indisponível para credenciais (%s): mantém envio.',
            exc,
        )
    payload = build_email_credenciais_payload(
        email_destino=email_destino,
        username=username,
        senha_plana=senha_plana,
        nome_completo=nome_completo,
        site_url=site_url,
    )
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or settings.EMAIL_HOST_USER
    destinatarios = payload['destinatarios']
    assunto = payload['assunto']
    mensagem_texto = payload['mensagem_texto']
    html_content = payload['html_content']
    email_log = _criar_log_email('credenciais_usuario', None, destinatarios, assunto)
    try:
        email = EmailMultiAlternatives(
            subject=assunto,
            body=mensagem_texto,
            from_email=from_email,
            to=destinatarios,
        )
        email.attach_alternative(html_content, "text/html")
        sucesso = _enviar_email_com_retry(email, email_log)
        if sucesso:
            logger.info(f"E-mail com credenciais enviado para {email_destino} (usuário: {username}).")
        else:
            logger.warning(f"Falha ao enviar e-mail de credenciais para {email_destino} (usuário: {username}).")
        return sucesso
    except Exception as e:
        if email_log:
            try:
                email_log.marcar_como_falhou(str(e))
            except Exception:
                pass
        logger.warning(f"Falha ao enviar e-mail de credenciais para {email_destino}: {e}")
        return False


def enviar_email_novo_pedido(workorder):
    """
    Envia e-mail para aprovadores da obra quando um novo pedido é criado.
    """
    # Verificar se email está configurado
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        logger.warning(
            f"Email não configurado. Não foi possível enviar email para novo pedido {workorder.codigo}. "
            f"Configure EMAIL_HOST_USER e EMAIL_HOST_PASSWORD nas variáveis de ambiente."
        )
        return False
    
    payload = build_email_novo_pedido_payload(workorder)
    destinatarios = payload['destinatarios']
    if not destinatarios:
        logger.info(
            'Nenhum destinatário após preferências de comunicação para novo pedido %s.',
            workorder.codigo,
        )
        return False
    assunto = payload['assunto']
    mensagem_texto = payload['mensagem_texto']
    html_content = payload['html_content']
    
    # Criar log de email ANTES de tentar enviar
    email_log = _criar_log_email('novo_pedido', workorder, destinatarios, assunto)
    
    try:
        # Usar EmailMultiAlternatives para enviar HTML + texto
        email = EmailMultiAlternatives(
            subject=assunto,
            body=mensagem_texto,
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else settings.EMAIL_HOST_USER,
            to=destinatarios,
        )
        email.attach_alternative(html_content, "text/html")
        
        # Enviar com retry
        sucesso = _enviar_email_com_retry(email, email_log)
        
        if sucesso:
            logger.info(f"Email de novo pedido enviado com sucesso para {destinatarios} - Pedido: {workorder.codigo}")
        else:
            logger.error(f"Falha ao enviar email de novo pedido {workorder.codigo} após múltiplas tentativas")
        
        return sucesso
    except Exception as e:
        # Registrar erro no log (se existir)
        if email_log:
            try:
                email_log.marcar_como_falhou(str(e))
            except Exception as log_error:
                logger.warning(f"Erro ao atualizar log de falha: {log_error}")
        logger.error(f"Erro ao enviar e-mail de novo pedido {workorder.codigo}: {e}", exc_info=True)
        return False


def _anexar_pdfs_individuais_email_aprovacao(email, workorder):
    """
    Fallback quando o PDF consolidado não pôde ser gerado.
    Mesma seleção e ordem do pacote aprovado (versão vigente, sem histórico reprovado).
    Anexa apenas arquivos PDF individuais.
    """
    from gestao_aprovacao.services.consolidated_signature_pdf import (
        PDF_EXT,
        _attachment_ext,
        ordered_attachments_for_consolidation,
    )

    attachments = [
        att
        for att in ordered_attachments_for_consolidation(workorder)
        if att.arquivo and _attachment_ext(att) == PDF_EXT
    ]

    anexos_anexados = 0
    anexos_falhados = 0

    for attachment in attachments:
        try:
            if not attachment.arquivo:
                anexos_falhados += 1
                continue
            try:
                arquivo_path = attachment.arquivo.path
            except ValueError:
                try:
                    arquivo_content = attachment.arquivo.read()
                    nome_arquivo = os.path.basename(attachment.arquivo.name)
                    email.attach(nome_arquivo, arquivo_content)
                    anexos_anexados += 1
                    continue
                except Exception as read_error:
                    logger.warning(
                        'Erro ao ler anexo remoto %s: %s',
                        attachment.arquivo.name,
                        read_error,
                    )
                    anexos_falhados += 1
                    continue

            if not os.path.exists(arquivo_path):
                anexos_falhados += 1
                continue

            with open(arquivo_path, 'rb') as f:
                arquivo_content = f.read()
                nome_arquivo = os.path.basename(arquivo_path)
                nome_arquivo_sanitizado = ''.join(
                    char for char in nome_arquivo
                    if ord(char) >= 32 or char in ['\n', '\r', '\t']
                )
                if not nome_arquivo_sanitizado.strip():
                    nome_arquivo_sanitizado = f'anexo_{attachment.pk}.pdf'
                email.attach(nome_arquivo_sanitizado, arquivo_content)
                anexos_anexados += 1
        except Exception as e:
            logger.warning(
                'Erro ao anexar PDF %s no fallback do pedido %s: %s',
                attachment.arquivo.name if attachment.arquivo else 'N/A',
                workorder.codigo,
                e,
            )
            anexos_falhados += 1

    return anexos_anexados, anexos_falhados


def build_email_aprovacao_payload(workorder, aprovado_por, comentario=None):
    """
    Monta payload do e-mail de aprovação (destinatários, assunto, texto e HTML),
    sem enviar. Pode ser usado por preview local.
    """
    solicitante = workorder.criado_por

    # Destinatários: solicitante (tipo próprio) + cópias administrativas (router piloto)
    dest_solicitante = []
    if solicitante and solicitante.email:
        dest_solicitante.append(solicitante.email)

    dest_admin = []
    if hasattr(settings, 'EMAIL_DEPARTAMENTOS_APROVACAO') and settings.EMAIL_DEPARTAMENTOS_APROVACAO:
        dest_admin.extend(settings.EMAIL_DEPARTAMENTOS_APROVACAO)
    dest_admin.extend(_get_destinatarios_fixos_aprovacao_para_obra(workorder.obra))

    dest_admin = _normalizar_destinatarios(dest_admin)
    solicitante_set = {e.lower() for e in dest_solicitante}
    dest_admin = [e for e in dest_admin if e.lower() not in solicitante_set]

    from core.comunicacao_constants import (
        TIPO_GESTCONTROLL_APROVADO_SOLICITANTE,
        TIPO_GESTCONTROLL_COPIA_ADMIN,
    )

    ctx = {
        'modulo': 'gestcontroll',
        'objeto_tipo': 'work_order',
        'objeto_id': workorder.pk,
    }
    dest_solicitante = _filtrar_destinatarios_router(
        dest_solicitante,
        TIPO_GESTCONTROLL_APROVADO_SOLICITANTE,
        contexto={**ctx, 'origem': 'aprovacao_solicitante'},
    )
    dest_admin = _filtrar_destinatarios_router(
        dest_admin,
        TIPO_GESTCONTROLL_COPIA_ADMIN,
        contexto={**ctx, 'origem': 'copia_administrativa_aprovacao'},
    )

    destinatarios = _normalizar_destinatarios(dest_solicitante + dest_admin)

    assunto = f'Pedido Aprovado: {workorder.codigo}'
    url_detalhes = _build_workorder_detail_url(workorder)
    aprovador_nome = aprovado_por.get_full_name() or aprovado_por.username
    data_aprovacao_str = (
        workorder.data_aprovacao.strftime('%d/%m/%Y %H:%M')
        if workorder.data_aprovacao
        else 'N/A'
    )

    mensagem_texto = f"""Pedido aprovado — {workorder.codigo}

O pedido {workorder.codigo} foi aprovado por {aprovador_nome} em {data_aprovacao_str}.

Pedido: {workorder.codigo}
Obra: {workorder.obra.nome} ({workorder.obra.codigo})
Credor: {workorder.nome_credor}
Tipo: {workorder.get_tipo_solicitacao_display()}
Aprovado por: {aprovador_nome}
Data de aprovação: {data_aprovacao_str}
"""
    if comentario:
        mensagem_texto += f"\nComentário do aprovador:\n{comentario}\n\n"
    mensagem_texto += f"""O PDF consolidado com todos os anexos do pedido e a assinatura do aprovador está anexo a este e-mail.

Ver detalhes no sistema: {url_detalhes}

Atenciosamente,

GestControll
Mensagem automática. Não responda a este e-mail.
"""

    comentario_html = ""
    if comentario:
        comentario_html = f"""
                <div class="comentario-box">
                    <strong>Comentário do aprovador</strong><br>
                    {comentario}
                </div>
        """
    conteudo_html = f"""
                <p>O pedido <strong>{workorder.codigo}</strong> foi aprovado por <strong>{aprovador_nome}</strong> em {data_aprovacao_str}.</p>
                {comentario_html}
                <p>O PDF consolidado com todos os anexos do pedido e a assinatura do aprovador está anexo a este e-mail. Use o botão abaixo para abrir o pedido no sistema.</p>
                <div class="info-box">
                    <div class="info-row">
                        <span class="info-label">Aprovado por</span>
                        <span class="info-value">{aprovador_nome}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Data de aprovação</span>
                        <span class="info-value">{data_aprovacao_str}</span>
                    </div>
                </div>
        """
    html_content = _gerar_html_email("Pedido Aprovado", conteudo_html, workorder, url_detalhes)

    return {
        'destinatarios': destinatarios,
        'assunto': assunto,
        'mensagem_texto': mensagem_texto,
        'html_content': html_content,
    }


def build_email_reprovacao_payload(workorder, aprovado_por, comentario):
    """Monta payload (destino/assunto/texto/html) do e-mail de reprovação."""
    solicitante = workorder.criado_por
    from core.comunicacao_constants import TIPO_GESTCONTROLL_REPROVADO_SOLICITANTE

    destinatarios = _filtrar_destinatarios_router(
        [solicitante.email] if solicitante and getattr(solicitante, 'email', None) else [],
        TIPO_GESTCONTROLL_REPROVADO_SOLICITANTE,
        contexto={
            'modulo': 'gestcontroll',
            'objeto_tipo': 'work_order',
            'objeto_id': workorder.pk,
            'origem': 'reprovacao_solicitante',
        },
    )
    assunto = f'Pedido Reprovado: {workorder.codigo}'
    url_detalhes = _build_workorder_detail_url(workorder)
    aprovado_por_nome = aprovado_por.get_full_name() or aprovado_por.username
    data_reprovacao = workorder.data_aprovacao.strftime('%d/%m/%Y %H:%M') if workorder.data_aprovacao else 'N/A'
    mensagem_texto = f"""
Seu pedido de obra foi reprovado.

Pedido: {workorder.codigo}
Obra: {workorder.obra.nome} ({workorder.obra.codigo})
Credor: {workorder.nome_credor}
Tipo: {workorder.get_tipo_solicitacao_display()}
Reprovado por: {aprovado_por_nome}
Data de reprovação: {data_reprovacao}

Motivo da reprovação:
{comentario}

Acesse o sistema para visualizar os detalhes:
{url_detalhes}

Atenciosamente,

GestControll
Mensagem automática. Não responda a este e-mail.
"""
    conteudo_html = f"""
                <p style="font-size: 18px; color: #721c24; font-weight: 600; margin-bottom: 20px;">
                    Seu pedido de obra foi <strong>reprovado</strong>.
                </p>
                <div class="comentario-box">
                    <strong>Motivo da Reprovação:</strong>
                    <p style="margin: 10px 0 0 0;">{comentario}</p>
                </div>
                <div class="info-row">
                    <span class="info-label">Reprovado por:</span>
                    <span class="info-value">{aprovado_por_nome}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Data de Reprovação:</span>
                    <span class="info-value">{data_reprovacao}</span>
                </div>
        """
    html_content = _gerar_html_email("Pedido Reprovado", conteudo_html, workorder, url_detalhes)
    return {
        'destinatarios': destinatarios,
        'assunto': assunto,
        'mensagem_texto': mensagem_texto,
        'html_content': html_content,
    }


def build_email_diario_obra_payload(diary):
    """Monta payload de preview para e-mail de diário enviado à lista da obra."""
    from core.comunicacao_constants import TIPO_RDO_LISTA_INTERNA

    project = diary.project
    target_date = diary.date
    link = f"{(getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/'))}{reverse('diary-detail', kwargs={'pk': diary.pk})}"
    destinatarios = list(project.diary_recipients.values_list('email', flat=True))
    destinatarios = _filtrar_destinatarios_router(
        destinatarios,
        TIPO_RDO_LISTA_INTERNA,
        contexto={
            'modulo': 'rdo',
            'objeto_tipo': 'construction_diary',
            'objeto_id': diary.pk,
            'origem': 'rdo_envio_lista_interna_preview',
        },
    )
    assunto = f"Diário de Obra (detalhado) - {project.name} - {target_date.strftime('%d/%m/%Y')}"
    mensagem_texto = f"""Prezado(a) senhor(a),

Segue em anexo o diário de obra detalhado referente ao dia {target_date.strftime('%d/%m/%Y')} da obra {project.name} ({project.code or ''}).

Para visualizar no sistema: {link}

Atenciosamente,

LPLAN - Diário de Obra
Mensagem automática. Não responda a este e-mail.
"""
    conteudo_html = f"""
                <p>Segue em anexo o diário de obra detalhado referente ao dia <strong>{target_date.strftime('%d/%m/%Y')}</strong>.</p>
                <div class="info-box">
                    <div class="info-row">
                        <span class="info-label">Obra</span>
                        <span class="info-value">{project.name} ({project.code or '—'})</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Diário</span>
                        <span class="info-value">#{diary.pk}</span>
                    </div>
                </div>
                <p>No envio real, o PDF detalhado do diário será anexado automaticamente.</p>
    """
    html_content = _gerar_html_email("Diário de Obra", conteudo_html, None, link)
    return {
        'destinatarios': destinatarios,
        'assunto': assunto,
        'mensagem_texto': mensagem_texto,
        'html_content': html_content,
    }


def build_email_diario_dono_obra_payload(diary):
    """Monta payload de preview para e-mail de diário enviado aos donos da obra."""
    from core.comunicacao_constants import TIPO_RDO_CLIENTE
    from core.models import ProjectOwner
    from core.diary_email import _pode_enviar_com_router

    project = diary.project
    target_date = diary.date
    link = f"{(getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/'))}{reverse('client-diary-detail', kwargs={'pk': diary.pk})}"
    owners = ProjectOwner.objects.filter(project=diary.project).select_related('user')
    destinatarios = []
    for po in owners:
        email_addr = (po.user.email or '').strip().lower()
        if not email_addr:
            continue
        if _pode_enviar_com_router(
            email_addr,
            TIPO_RDO_CLIENTE,
            contexto={
                'modulo': 'rdo',
                'objeto_tipo': 'construction_diary',
                'objeto_id': diary.pk,
                'origem': 'rdo_envio_cliente_preview',
            },
            usuario=po.user,
        ):
            destinatarios.append(email_addr)
    destinatarios = _normalizar_destinatarios(destinatarios)
    assunto = f"Diário de Obra - {project.name} - {target_date.strftime('%d/%m/%Y')}"
    mensagem_texto = f"""Prezado(a),

Informamos que o diário de obra referente ao dia {target_date.strftime('%d/%m/%Y')} da obra {project.name} ({project.code}) foi aprovado e está disponível para visualização.

Para acessar o documento e enviar comentários, utilize o link abaixo:

{link}

Atenciosamente,

LPLAN - Diário de Obra
Mensagem automática. Não responda a este e-mail.
"""
    conteudo_html = f"""
                <p>O diário de obra de <strong>{target_date.strftime('%d/%m/%Y')}</strong> foi aprovado e está disponível para visualização.</p>
                <div class="info-box">
                    <div class="info-row">
                        <span class="info-label">Obra</span>
                        <span class="info-value">{project.name} ({project.code})</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Diário</span>
                        <span class="info-value">#{diary.pk}</span>
                    </div>
                </div>
                <p>Use o botão abaixo para abrir o diário no portal do cliente.</p>
    """
    html_content = _gerar_html_email("Diário de Obra Aprovado", conteudo_html, None, link)
    return {
        'destinatarios': destinatarios,
        'assunto': assunto,
        'mensagem_texto': mensagem_texto,
        'html_content': html_content,
    }


def _enviar_email_aprovacao_thread(workorder_id, aprovado_por_id, comentario):
    """
    Função interna que roda em thread para enviar email de aprovação com anexos.
    Não deve ser chamada diretamente - use enviar_email_aprovacao().
    """
    from .models import WorkOrder

    try:
        # Recarregar objetos do banco (necessário em threads)
        from django.contrib.auth.models import User
        workorder = WorkOrder.objects.get(pk=workorder_id)
        aprovado_por = User.objects.get(pk=aprovado_por_id)
        
        # Verificar se email está configurado
        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            logger.warning(
                f"Email não configurado. Não foi possível enviar email de aprovação para pedido {workorder.codigo}. "
                f"Configure EMAIL_HOST_USER e EMAIL_HOST_PASSWORD nas variáveis de ambiente."
            )
            return False
        
        payload = build_email_aprovacao_payload(workorder, aprovado_por, comentario)
        destinatarios = payload['destinatarios']
        
        if not destinatarios:
            logger.warning(f"Nenhum destinatário encontrado para email de aprovação do pedido {workorder.codigo}.")
            return False
        assunto = payload['assunto']
        mensagem_texto = payload['mensagem_texto']
        html_content = payload['html_content']
        
        # Criar log de email ANTES de tentar enviar
        email_log = _criar_log_email('aprovacao', workorder, destinatarios, assunto)
        
        # Criar EmailMultiAlternatives para poder anexar arquivos e enviar HTML
        email = EmailMultiAlternatives(
            subject=assunto,
            body=mensagem_texto,
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else settings.EMAIL_HOST_USER,
            to=destinatarios,
        )
        email.attach_alternative(html_content, "text/html")

        from gestao_aprovacao.services.consolidated_signature_pdf import (
            try_build_consolidated_approval_email_pdf,
        )

        anexos_anexados = 0
        anexos_falhados = 0
        consolidated = try_build_consolidated_approval_email_pdf(workorder)

        if consolidated:
            pdf_bytes, nome_arquivo = consolidated
            tamanho = len(pdf_bytes)
            if tamanho > 25 * 1024 * 1024:
                logger.warning(
                    'PDF consolidado do pedido %s muito grande (%.2f MB); '
                    'e-mail pode falhar no envio.',
                    workorder.codigo,
                    tamanho / 1024 / 1024,
                )
            email.attach(nome_arquivo, pdf_bytes, 'application/pdf')
            anexos_anexados = 1
            logger.info(
                'E-mail de aprovação do pedido %s: anexo PDF consolidado %s (%d bytes).',
                workorder.codigo,
                nome_arquivo,
                tamanho,
            )
        else:
            logger.warning(
                'PDF consolidado indisponível para pedido %s; usando fallback de PDFs individuais.',
                workorder.codigo,
            )
            anexos_anexados, anexos_falhados = _anexar_pdfs_individuais_email_aprovacao(
                email, workorder
            )

        if anexos_anexados == 0:
            logger.info(
                'Nenhum anexo no e-mail de aprovação do pedido %s (consolidado e fallback vazios).',
                workorder.codigo,
            )
        
        # Enviar email com retry
        try:
            sucesso = _enviar_email_com_retry(email, email_log)
            
            if sucesso:
                logger.info(
                    f"Email de aprovação enviado com sucesso para {destinatarios} - Pedido: {workorder.codigo}. "
                    f"Anexos: {anexos_anexados} anexados, {anexos_falhados} falhados."
                )
            else:
                logger.error(
                    f"Falha ao enviar email de aprovação {workorder.codigo} após múltiplas tentativas. "
                    f"Anexos: {anexos_anexados} anexados, {anexos_falhados} falhados."
                )
            
            return sucesso
        except Exception as e:
            # Registrar erro no log (se existir)
            if email_log:
                try:
                    email_log.marcar_como_falhou(str(e))
                except Exception as log_error:
                    logger.warning(f"Erro ao atualizar log de falha: {log_error}")
            logger.error(f"Erro ao enviar email de aprovação {workorder.codigo}: {e}", exc_info=True)
            return False
        
    except Exception as e:
        logger.error(f"Erro ao enviar e-mail de aprovação {workorder_id}: {e}", exc_info=True)
        return False


def enviar_email_aprovacao(workorder, aprovado_por, comentario=None):
    """
    Envia e-mail para o solicitante e departamentos quando o pedido é aprovado.
    Anexa o PDF consolidado (todos os anexos + assinatura do aprovador), com fallback
    para PDFs individuais apenas se a consolidação não for possível.
    Roda em thread separada para não travar a interface.
    
    Args:
        workorder: Instância do WorkOrder aprovado
        aprovado_por: Usuário que aprovou o pedido
        comentario: Comentário opcional da aprovação
    
    Returns:
        None (executa em background)
    """
    # Verificar se email está configurado antes de criar thread
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        logger.warning(
            f"Email não configurado. Não foi possível enviar email de aprovação para pedido {workorder.codigo}. "
            f"Configure EMAIL_HOST_USER e EMAIL_HOST_PASSWORD nas variáveis de ambiente."
        )
        return False
    
    # Salvar IDs para passar para a thread (evita problemas com objetos do Django em threads)
    workorder_id = workorder.pk
    aprovado_por_id = aprovado_por.pk
    
    # Criar e iniciar thread em background.
    # Em alguns hosts compartilhados pode haver limite de threads por processo.
    # Se isso acontecer, fazemos fallback síncrono para evitar erro 500 na aprovação.
    thread = threading.Thread(
        target=_enviar_email_aprovacao_thread,
        args=(workorder_id, aprovado_por_id, comentario),
        daemon=True  # Thread daemon não impede o programa de encerrar
    )
    try:
        thread.start()
        logger.info(f"Thread de envio de email de aprovação iniciada para pedido {workorder.codigo}")
        return True
    except RuntimeError as exc:
        logger.warning(
            "Não foi possível iniciar thread de e-mail para pedido %s (%s). "
            "Executando envio síncrono como fallback.",
            workorder.codigo,
            exc,
        )
        return _enviar_email_aprovacao_thread(workorder_id, aprovado_por_id, comentario)


def enviar_email_reprovacao(workorder, aprovado_por, comentario):
    """
    Envia e-mail para o solicitante quando o pedido é reprovado.
    """
    # Verificar se email está configurado
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        logger.warning(
            f"Email não configurado. Não foi possível enviar email de reprovação para pedido {workorder.codigo}. "
            f"Configure EMAIL_HOST_USER e EMAIL_HOST_PASSWORD nas variáveis de ambiente."
        )
        return False
    
    solicitante = workorder.criado_por
    if not solicitante or not getattr(solicitante, 'email', None):
        logger.warning(f"Pedido {workorder.codigo}: solicitante sem e-mail. Email de reprovação não enviado.")
        return False

    payload = build_email_reprovacao_payload(workorder, aprovado_por, comentario)
    dest_reprov = payload['destinatarios']
    if not dest_reprov:
        logger.info(
            'E-mail de reprovação não enviado para %s (preferências de comunicação).',
            workorder.codigo,
        )
        return False
    assunto = payload['assunto']
    mensagem_texto = payload['mensagem_texto']
    html_content = payload['html_content']
    
    # Criar log de email ANTES de tentar enviar
    email_log = _criar_log_email('reprovacao', workorder, dest_reprov, assunto)
    
    try:
        # Usar EmailMultiAlternatives para enviar HTML + texto
        email = EmailMultiAlternatives(
            subject=assunto,
            body=mensagem_texto,
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else settings.EMAIL_HOST_USER,
            to=dest_reprov,
        )
        email.attach_alternative(html_content, "text/html")
        
        # Enviar com retry
        sucesso = _enviar_email_com_retry(email, email_log)
        
        if sucesso:
            logger.info(f"Email de reprovação enviado com sucesso para {solicitante.email} - Pedido: {workorder.codigo}")
        else:
            logger.error(f"Falha ao enviar email de reprovação {workorder.codigo} após múltiplas tentativas")
        
        return sucesso
    except Exception as e:
        # Registrar erro no log (se existir)
        if email_log:
            try:
                email_log.marcar_como_falhou(str(e))
            except Exception as log_error:
                logger.warning(f"Erro ao atualizar log de falha: {log_error}")
        logger.error(f"Erro ao enviar e-mail de reprovação {workorder.codigo}: {e}", exc_info=True)
        return False

