"""
Utilitários para envio de e-mails de notificação.
"""
import logging
import threading
import os
import time
from django.core.mail import send_mail, EmailMessage, EmailMultiAlternatives
from django.conf import settings
from django.utils.html import strip_tags
from django.utils import timezone

logger = logging.getLogger(__name__)


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
                border-radius: 6px;
                overflow: hidden;
            }}
            .email-header {{
                padding: 20px 24px;
                border-bottom: 1px solid #e5e7eb;
            }}
            .email-header h1 {{
                margin: 0;
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
                padding: 10px 20px;
                background: #111827;
                color: #ffffff !important;
                text-decoration: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: 500;
            }}
            .email-footer {{
                padding: 16px 24px;
                border-top: 1px solid #f3f4f6;
                font-size: 12px;
                color: #9ca3af;
            }}
            .email-footer p {{
                margin: 0;
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
                <p>GestControll - Mensagem automática. Não responda a este e-mail.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html


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
    url = site_url or getattr(settings, 'SITE_URL', None) or 'https://lplan.com.br'
    nome = (nome_completo or username).strip()
    assunto = 'Acesso ao sistema LPlan - seus dados de login'
    corpo = f"""Olá, {nome}.

Foi criada uma conta de acesso ao sistema LPlan para você.

DADOS DE ACESSO:
----------------
Login:    {username}
Senha:    {senha_plana}

URL do sistema: {url}

Recomendamos que você altere sua senha no primeiro acesso (Perfil ou Configurações).

Este é um e-mail automático. Em caso de dúvidas, entre em contato com o administrador do sistema.
"""
    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or settings.EMAIL_HOST_USER
        send_mail(
            assunto,
            corpo,
            from_email,
            [email_destino.strip()],
            fail_silently=True,
        )
        logger.info(f"E-mail com credenciais enviado para {email_destino} (usuário: {username}).")
        return True
    except Exception as e:
        logger.warning(f"Falha ao enviar e-mail de credenciais para {email_destino}: {e}")
        return False


def enviar_email_novo_pedido(workorder):
    """
    Envia e-mail para aprovadores da obra quando um novo pedido é criado.
    """
    from .models import WorkOrderPermission
    
    # Verificar se email está configurado
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        logger.warning(
            f"Email não configurado. Não foi possível enviar email para novo pedido {workorder.codigo}. "
            f"Configure EMAIL_HOST_USER e EMAIL_HOST_PASSWORD nas variáveis de ambiente."
        )
        return False
    
    obra = workorder.obra
    # Obter aprovadores com permissão ativa na obra
    permissoes_aprovadores = WorkOrderPermission.objects.filter(
        obra=obra,
        tipo_permissao='aprovador',
        ativo=True
    ).select_related('usuario')
    
    aprovadores = [p.usuario for p in permissoes_aprovadores if p.usuario.is_active]
    
    if not aprovadores:
        logger.debug(f"Nenhum aprovador encontrado para obra {obra.codigo}. Email não enviado.")
        return False
    
    # Lista de destinatários
    destinatarios = [a.email for a in aprovadores if a.email]
    
    # Se a obra tem e-mail, adicionar também
    if obra.email_obra:
        destinatarios.append(obra.email_obra)
    
    if not destinatarios:
        logger.warning(f"Nenhum email de destinatário encontrado para pedido {workorder.codigo}.")
        return False
    
    # Assunto
    assunto = f'Novo Pedido Pendente: {workorder.codigo} - {obra.nome}'
    
    # URL para detalhes
    url_detalhes = f"{getattr(settings, 'SITE_URL', 'https://gestao.lplan.com.br')}/pedidos/{workorder.pk}/"
    
    # Corpo do e-mail (texto simples)
    mensagem_texto = f"""
Um novo pedido de obra foi criado e está aguardando sua aprovação.

Pedido: {workorder.codigo}
Obra: {obra.nome} ({obra.codigo})
Credor: {workorder.nome_credor}
Tipo: {workorder.get_tipo_solicitacao_display()}
Solicitante: {workorder.criado_por.get_full_name() or workorder.criado_por.username}
E-mail do Solicitante: {workorder.criado_por.email}
Data de Envio: {workorder.data_envio.strftime('%d/%m/%Y %H:%M') if workorder.data_envio else 'N/A'}

Observações:
{workorder.observacoes or 'Nenhuma observação'}

Acesse o sistema para aprovar ou reprovar este pedido:
{url_detalhes}

Atenciosamente,

GestControll
Mensagem automática. Não responda a este e-mail.
"""
    
    # Corpo do e-mail (HTML)
    observacoes_html = f"<p><strong>Observações:</strong><br>{workorder.observacoes or 'Nenhuma observação'}</p>" if workorder.observacoes else ""
    conteudo_html = f"""
                <p>Um novo pedido de obra foi criado e está <strong>aguardando sua aprovação</strong>.</p>
                {observacoes_html}
                <div class="info-row">
                    <span class="info-label">Data de Envio:</span>
                    <span class="info-value">{workorder.data_envio.strftime('%d/%m/%Y %H:%M') if workorder.data_envio else 'N/A'}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">E-mail do Solicitante:</span>
                    <span class="info-value">{workorder.criado_por.email}</span>
                </div>
    """
    
    html_content = _gerar_html_email("Novo Pedido Pendente", conteudo_html, workorder, url_detalhes)
    
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


def _enviar_email_aprovacao_thread(workorder_id, aprovado_por_id, comentario):
    """
    Função interna que roda em thread para enviar email de aprovação com anexos.
    Não deve ser chamada diretamente - use enviar_email_aprovacao().
    """
    from .models import WorkOrder, Attachment
    
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
        
        solicitante = workorder.criado_por
        
        # Montar lista de destinatários
        destinatarios = []
        
        # Adicionar solicitante
        if solicitante.email:
            destinatarios.append(solicitante.email)
        
        # Adicionar departamentos configurados
        if hasattr(settings, 'EMAIL_DEPARTAMENTOS_APROVACAO') and settings.EMAIL_DEPARTAMENTOS_APROVACAO:
            for email_dept in settings.EMAIL_DEPARTAMENTOS_APROVACAO:
                if email_dept and email_dept not in destinatarios:
                    destinatarios.append(email_dept)
        
        # Remover duplicatas mantendo ordem
        destinatarios = list(dict.fromkeys(destinatarios))
        
        if not destinatarios:
            logger.warning(f"Nenhum destinatário encontrado para email de aprovação do pedido {workorder.codigo}.")
            return False
        
        # Preparar assunto e mensagem
        assunto = f'Pedido Aprovado: {workorder.codigo}'
        
        # URL para detalhes
        url_detalhes = f"{getattr(settings, 'SITE_URL', 'https://gestao.lplan.com.br')}/pedidos/{workorder.pk}/"
        
        aprovador_nome = aprovado_por.get_full_name() or aprovado_por.username
        data_aprovacao_str = workorder.data_aprovacao.strftime('%d/%m/%Y %H:%M') if workorder.data_aprovacao else 'N/A'

        # Corpo do e-mail (texto simples) — formato limpo
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
        mensagem_texto += f"""Os documentos aprovados estão anexados a este e-mail.

Ver detalhes no sistema: {url_detalhes}

Atenciosamente,

GestControll
Mensagem automática. Não responda a este e-mail.
"""

        # Corpo do e-mail (HTML) — visual neutro, sem destaque colorido
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
                <p>Os documentos aprovados estão anexados a este e-mail. Use o botão abaixo para abrir o pedido no sistema.</p>
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
        
        # Buscar a última aprovação para filtrar apenas anexos da versão aprovada
        from .models import Approval
        ultima_aprovacao = Approval.objects.filter(
            work_order=workorder,
            decisao='aprovado'
        ).order_by('-created_at').first()
        
        # Buscar a última reprovação (se houver) para excluir anexos de versões reprovadas
        ultima_reprovacao = Approval.objects.filter(
            work_order=workorder,
            decisao='reprovado'
        ).order_by('-created_at').first()
        
        # Filtrar anexos:
        # 1. Apenas PDFs (não imagens)
        # 2. Apenas anexos da versão aprovada (criados após a última reprovação, se houver)
        attachments_query = Attachment.objects.filter(work_order=workorder)
        
        # Lógica de filtragem por data:
        # - Se houver reprovação E ela for anterior à aprovação: enviar apenas anexos após a reprovação
        # - Se não houver reprovação OU reprovação for posterior à aprovação: enviar todos os anexos
        if ultima_reprovacao and ultima_aprovacao:
            # Se a reprovação foi antes da aprovação, filtrar anexos após a reprovação
            if ultima_reprovacao.created_at < ultima_aprovacao.created_at:
                attachments_query = attachments_query.filter(created_at__gte=ultima_reprovacao.created_at)
                logger.debug(
                    f"Filtrando anexos após reprovação ({ultima_reprovacao.created_at}) "
                    f"para pedido {workorder.codigo}"
                )
        elif ultima_reprovacao and not ultima_aprovacao:
            # Caso estranho: há reprovação mas não há aprovação (não deveria acontecer, mas tratamos)
            logger.warning(
                f"Pedido {workorder.codigo} tem reprovação mas não tem aprovação. "
                f"Não enviando anexos por segurança."
            )
            attachments_query = Attachment.objects.none()
        
        # Filtrar apenas PDFs (extensões de imagem serão excluídas)
        # Extensões de imagem que NÃO queremos: .jpg, .jpeg, .png, .gif
        extensoes_imagem = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']
        attachments = []
        for att in attachments_query:
            if not att.arquivo:
                continue
            try:
                # Obter extensão do arquivo de forma segura
                nome_arquivo = att.arquivo.name.lower()
                extensao = os.path.splitext(nome_arquivo)[1].lower()
                
                # Incluir apenas PDFs (excluir imagens e outros tipos)
                if extensao == '.pdf':
                    attachments.append(att)
                    logger.debug(f"PDF incluído no email: {nome_arquivo}")
                elif extensao in extensoes_imagem:
                    logger.debug(f"Imagem excluída do email: {nome_arquivo} (apenas PDFs são enviados)")
                else:
                    logger.debug(f"Arquivo excluído do email: {nome_arquivo} (tipo {extensao} não é PDF)")
            except Exception as e:
                logger.warning(f"Erro ao processar anexo {att.pk} do pedido {workorder.codigo}: {e}")
                continue
        
        anexos_anexados = 0
        anexos_falhados = 0
        
        # Processar anexos PDFs
        for attachment in attachments:
            try:
                # Verificar se o arquivo existe no campo
                if not attachment.arquivo:
                    logger.warning(f"Anexo {attachment.pk} não tem arquivo associado")
                    anexos_falhados += 1
                    continue
                
                # Obter caminho completo do arquivo
                try:
                    arquivo_path = attachment.arquivo.path
                except ValueError as e:
                    # Arquivo pode estar em storage remoto (S3, etc)
                    logger.warning(f"Não foi possível obter path local do arquivo {attachment.arquivo.name}: {e}")
                    # Tentar ler diretamente do campo arquivo
                    try:
                        arquivo_content = attachment.arquivo.read()
                        nome_arquivo = os.path.basename(attachment.arquivo.name)
                        email.attach(nome_arquivo, arquivo_content)
                        anexos_anexados += 1
                        logger.debug(f"PDF anexado (storage remoto): {nome_arquivo} ({len(arquivo_content)} bytes)")
                        continue
                    except Exception as read_error:
                        logger.warning(f"Erro ao ler arquivo remoto {attachment.arquivo.name}: {read_error}")
                        anexos_falhados += 1
                        continue
                
                # Verificar se arquivo existe no sistema de arquivos
                if not os.path.exists(arquivo_path):
                    logger.warning(f"Arquivo não encontrado no sistema: {arquivo_path} - Anexo ID: {attachment.pk}")
                    anexos_falhados += 1
                    continue
                
                # Verificar tamanho do arquivo (evitar arquivos muito grandes)
                tamanho_arquivo = os.path.getsize(arquivo_path)
                if tamanho_arquivo > 25 * 1024 * 1024:  # 25MB (limite recomendado para email)
                    logger.warning(
                        f"Arquivo muito grande ({tamanho_arquivo / 1024 / 1024:.2f}MB): {arquivo_path}. "
                        f"Pode causar problemas no envio do email."
                    )
                
                # Ler arquivo e anexar
                with open(arquivo_path, 'rb') as f:
                    arquivo_content = f.read()
                    nome_arquivo = os.path.basename(arquivo_path)
                    # Sanitizar nome do arquivo removendo apenas caracteres problemáticos
                    # Manter acentos e caracteres especiais comuns, mas remover caracteres de controle
                    nome_arquivo_sanitizado = ''.join(
                        char for char in nome_arquivo 
                        if ord(char) >= 32 or char in ['\n', '\r', '\t']
                    )
                    # Se a sanitização removeu tudo, usar nome padrão
                    if not nome_arquivo_sanitizado.strip():
                        nome_arquivo_sanitizado = f"anexo_{attachment.pk}.pdf"
                    email.attach(nome_arquivo_sanitizado, arquivo_content)
                    anexos_anexados += 1
                    logger.debug(f"PDF anexado: {nome_arquivo_sanitizado} ({len(arquivo_content)} bytes)")
                    
            except OSError as e:
                # Erro de sistema de arquivos
                logger.warning(
                    f"Erro de sistema ao acessar arquivo {attachment.arquivo.name if attachment.arquivo else 'N/A'} "
                    f"do pedido {workorder.codigo}: {e}. Continuando envio do email sem este anexo."
                )
                anexos_falhados += 1
                continue
            except Exception as e:
                # Outros erros
                logger.warning(
                    f"Erro ao anexar arquivo {attachment.arquivo.name if attachment.arquivo else 'N/A'} "
                    f"do pedido {workorder.codigo}: {e}. Continuando envio do email sem este anexo."
                )
                anexos_falhados += 1
                continue
        
        # Log informativo sobre anexos
        if anexos_anexados == 0:
            if len(attachments) > 0:
                logger.info(
                    f"Nenhum PDF foi anexado ao email do pedido {workorder.codigo} "
                    f"(todos falharam ou não foram encontrados). Email será enviado sem anexos."
                )
            else:
                logger.info(
                    f"Nenhum PDF encontrado para anexar ao email do pedido {workorder.codigo}. "
                    f"Email será enviado sem anexos."
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
    Inclui todos os anexos do pedido.
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
    
    # Criar e iniciar thread em background
    thread = threading.Thread(
        target=_enviar_email_aprovacao_thread,
        args=(workorder_id, aprovado_por_id, comentario),
        daemon=True  # Thread daemon não impede o programa de encerrar
    )
    thread.start()
    
    logger.info(f"Thread de envio de email de aprovação iniciada para pedido {workorder.codigo}")
    return True


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
    
    if not solicitante.email:
        logger.warning(f"Solicitante {solicitante.username} não tem email cadastrado. Email de reprovação não enviado.")
        return False
    
    assunto = f'Pedido Reprovado: {workorder.codigo}'
    
    # URL para detalhes
    url_detalhes = f"{getattr(settings, 'SITE_URL', 'https://gestao.lplan.com.br')}/pedidos/{workorder.pk}/"
    
    # Corpo do e-mail (texto simples)
    mensagem_texto = f"""
Seu pedido de obra foi reprovado.

Pedido: {workorder.codigo}
Obra: {workorder.obra.nome} ({workorder.obra.codigo})
Credor: {workorder.nome_credor}
Tipo: {workorder.get_tipo_solicitacao_display()}
Reprovado por: {aprovado_por.get_full_name() or aprovado_por.username}
Data de reprovação: {workorder.data_aprovacao.strftime('%d/%m/%Y %H:%M') if workorder.data_aprovacao else 'N/A'}

Motivo da reprovação:
{comentario}

Acesse o sistema para visualizar os detalhes:
{url_detalhes}

Atenciosamente,

GestControll
Mensagem automática. Não responda a este e-mail.
"""
    
    # Corpo do e-mail (HTML)
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
                    <span class="info-value">{aprovado_por.get_full_name() or aprovado_por.username}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Data de Reprovação:</span>
                    <span class="info-value">{workorder.data_aprovacao.strftime('%d/%m/%Y %H:%M') if workorder.data_aprovacao else 'N/A'}</span>
                </div>
        """
    
    html_content = _gerar_html_email("Pedido Reprovado", conteudo_html, workorder, url_detalhes)
    
    # Criar log de email ANTES de tentar enviar
    email_log = _criar_log_email('reprovacao', workorder, [solicitante.email], assunto)
    
    try:
        # Usar EmailMultiAlternatives para enviar HTML + texto
        email = EmailMultiAlternatives(
            subject=assunto,
            body=mensagem_texto,
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else settings.EMAIL_HOST_USER,
            to=[solicitante.email],
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

