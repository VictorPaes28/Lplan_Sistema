"""
Comando para verificar se o sistema está configurado para enviar emails.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend
from obras.models import EmailLog
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Verifica se o sistema está configurado para enviar emails'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('VERIFICAÇÃO DE CONFIGURAÇÃO DE EMAIL'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')
        
        # Verificar configurações
        self.stdout.write('Configurações atuais:')
        self.stdout.write(f'  EMAIL_BACKEND: {settings.EMAIL_BACKEND}')
        self.stdout.write(f'  EMAIL_HOST: {settings.EMAIL_HOST}')
        self.stdout.write(f'  EMAIL_PORT: {settings.EMAIL_PORT}')
        if hasattr(settings, 'EMAIL_USE_SSL'):
            self.stdout.write(f'  EMAIL_USE_SSL: {settings.EMAIL_USE_SSL}')
        if hasattr(settings, 'EMAIL_USE_TLS'):
            self.stdout.write(f'  EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}')
        
        email_user = settings.EMAIL_HOST_USER if settings.EMAIL_HOST_USER else '(VAZIO)'
        email_pass = '***' if settings.EMAIL_HOST_PASSWORD else '(VAZIO)'
        from_email = settings.DEFAULT_FROM_EMAIL if settings.DEFAULT_FROM_EMAIL else '(VAZIO)'
        
        if not settings.EMAIL_HOST_USER:
            self.stdout.write(self.style.WARNING(f'  EMAIL_HOST_USER: {email_user}'))
        else:
            self.stdout.write(f'  EMAIL_HOST_USER: {email_user}')
            
        if not settings.EMAIL_HOST_PASSWORD:
            self.stdout.write(self.style.WARNING(f'  EMAIL_HOST_PASSWORD: {email_pass}'))
        else:
            self.stdout.write(f'  EMAIL_HOST_PASSWORD: {email_pass}')
            
        self.stdout.write(f'  DEFAULT_FROM_EMAIL: {from_email}')
        self.stdout.write('')
        
        # Verificar se está configurado
        configurado = bool(settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD)
        
        if not configurado:
            self.stdout.write(self.style.ERROR('⚠️  ATENÇÃO: Email NÃO está configurado!'))
            self.stdout.write('')
            self.stdout.write('Para configurar o envio de emails, você precisa definir as seguintes')
            self.stdout.write('variáveis de ambiente no arquivo .env ou nas variáveis do sistema:')
            self.stdout.write('  - EMAIL_HOST_USER: Seu email (ex: seuemail@gmail.com)')
            self.stdout.write('  - EMAIL_HOST_PASSWORD: Sua senha ou senha de app')
            self.stdout.write('  - EMAIL_HOST: Servidor SMTP (padrão: smtp.gmail.com)')
            self.stdout.write('  - EMAIL_PORT: Porta SMTP (padrão: 587)')
            self.stdout.write('  - DEFAULT_FROM_EMAIL: Email remetente (opcional)')
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('O sistema está tentando enviar emails, mas eles falharão'))
            self.stdout.write(self.style.WARNING('porque as credenciais não estão configuradas.'))
            self.stdout.write('')
            self.stdout.write('RESPOSTA: NÃO, o sistema NÃO está enviando emails no momento.')
            return
        
        # Testar conexão
        self.stdout.write(self.style.SUCCESS('✓ Email está configurado com credenciais.'))
        self.stdout.write('')
        self.stdout.write('Testando conexão com servidor de email...')
        
        try:
            # Configurar SSL ou TLS conforme a porta
            use_ssl = getattr(settings, 'EMAIL_USE_SSL', False)
            use_tls = getattr(settings, 'EMAIL_USE_TLS', False)
            
            backend = EmailBackend(
                host=settings.EMAIL_HOST,
                port=settings.EMAIL_PORT,
                username=settings.EMAIL_HOST_USER,
                password=settings.EMAIL_HOST_PASSWORD,
                use_tls=use_tls,
                use_ssl=use_ssl,
            )
            backend.open()
            self.stdout.write(self.style.SUCCESS('✓ Conexão com servidor de email estabelecida com sucesso!'))
            backend.close()
            self.stdout.write('')
            
            # Verificar logs de email
            self.stdout.write('=' * 60)
            self.stdout.write('ESTATÍSTICAS DE ENVIO DE EMAILS')
            self.stdout.write('=' * 60)
            self.stdout.write('')
            
            total_logs = EmailLog.objects.count()
            enviados = EmailLog.objects.filter(status='enviado').count()
            falhados = EmailLog.objects.filter(status='falhou').count()
            pendentes = EmailLog.objects.filter(status='pendente').count()
            
            self.stdout.write(f'Total de emails registrados: {total_logs}')
            self.stdout.write(self.style.SUCCESS(f'  ✓ Enviados com sucesso: {enviados}'))
            if falhados > 0:
                self.stdout.write(self.style.ERROR(f'  ✗ Falhados: {falhados}'))
            else:
                self.stdout.write(f'  ✗ Falhados: {falhados}')
            if pendentes > 0:
                self.stdout.write(self.style.WARNING(f'  ⏳ Pendentes: {pendentes}'))
            else:
                self.stdout.write(f'  ⏳ Pendentes: {pendentes}')
            
            if total_logs > 0:
                taxa_sucesso = round((enviados / total_logs * 100), 1)
                self.stdout.write('')
                self.stdout.write(f'Taxa de sucesso: {taxa_sucesso}%')
                
                # Últimos 7 dias
                sete_dias_atras = timezone.now() - timedelta(days=7)
                logs_7d = EmailLog.objects.filter(criado_em__gte=sete_dias_atras)
                enviados_7d = logs_7d.filter(status='enviado').count()
                falhados_7d = logs_7d.filter(status='falhou').count()
                
                self.stdout.write('')
                self.stdout.write('Últimos 7 dias:')
                self.stdout.write(f'  Enviados: {enviados_7d}')
                self.stdout.write(f'  Falhados: {falhados_7d}')
                
                # Últimos emails falhados
                if falhados > 0:
                    self.stdout.write('')
                    self.stdout.write(self.style.WARNING('⚠️  ÚLTIMOS EMAILS FALHADOS:'))
                    ultimos_falhados = EmailLog.objects.filter(status='falhou').order_by('-criado_em')[:5]
                    for log in ultimos_falhados:
                        self.stdout.write(f'  - {log.assunto[:50]}... ({log.criado_em.strftime("%d/%m/%Y %H:%M")})')
                        if log.mensagem_erro:
                            erro_curto = log.mensagem_erro[:80] + '...' if len(log.mensagem_erro) > 80 else log.mensagem_erro
                            self.stdout.write(f'    Erro: {erro_curto}')
            else:
                self.stdout.write('')
                self.stdout.write(self.style.WARNING('⚠️  Nenhum email foi enviado ainda.'))
                self.stdout.write('   O sistema está pronto, mas ainda não há histórico de envios.')
            
            self.stdout.write('')
            self.stdout.write('=' * 60)
            self.stdout.write(self.style.SUCCESS('RESPOSTA: SIM, o sistema ESTÁ configurado e pronto para enviar emails.'))
            if total_logs > 0 and enviados > 0:
                self.stdout.write(self.style.SUCCESS(f'✓ Emails estão sendo enviados com sucesso! ({enviados} enviados)'))
            elif falhados > 0:
                self.stdout.write(self.style.WARNING('⚠️  Há emails falhando. Verifique os erros acima.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Erro ao conectar com servidor de email: {e}'))
            self.stdout.write('')
            self.stdout.write('Possíveis causas:')
            self.stdout.write('  - Credenciais incorretas')
            self.stdout.write('  - Servidor SMTP incorreto')
            self.stdout.write('  - Porta incorreta')
            self.stdout.write('  - Firewall bloqueando a conexão')
            self.stdout.write('  - Para Gmail: pode precisar de "Senha de App" ao invés da senha normal')
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('RESPOSTA: O sistema está configurado, mas há problemas na conexão.'))
            self.stdout.write(self.style.WARNING('Os emails podem não estar sendo enviados.'))
            
            # Mesmo com erro de conexão, mostrar estatísticas de logs
            try:
                total_logs = EmailLog.objects.count()
                if total_logs > 0:
                    self.stdout.write('')
                    self.stdout.write('=' * 60)
                    self.stdout.write('ESTATÍSTICAS DE ENVIO (mesmo com erro de conexão)')
                    self.stdout.write('=' * 60)
                    enviados = EmailLog.objects.filter(status='enviado').count()
                    falhados = EmailLog.objects.filter(status='falhou').count()
                    self.stdout.write(f'Total: {total_logs} | Enviados: {enviados} | Falhados: {falhados}')
            except Exception:
                pass

