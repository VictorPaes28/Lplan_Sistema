"""
Comando para verificar se emails foram enviados recentemente.
Verifica pedidos aprovados/reprovados e se há logs correspondentes.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from gestao_aprovacao.models import WorkOrder, Approval, EmailLog


class Command(BaseCommand):
    help = 'Verifica se emails foram enviados para pedidos recentes'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('VERIFICAÇÃO DE EMAILS ENVIADOS'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')
        
        # Verificar últimos 7 dias
        sete_dias_atras = timezone.now() - timedelta(days=7)
        
        # Pedidos aprovados nos últimos 7 dias
        aprovacoes = Approval.objects.filter(
            created_at__gte=sete_dias_atras,
            aprovado=True
        ).select_related('work_order', 'aprovado_por').order_by('-created_at')[:10]
        
        # Pedidos reprovados nos últimos 7 dias
        reprovacoes = Approval.objects.filter(
            created_at__gte=sete_dias_atras,
            aprovado=False
        ).select_related('work_order', 'aprovado_por').order_by('-created_at')[:10]
        
        self.stdout.write(f'📊 ÚLTIMOS 7 DIAS:')
        self.stdout.write('')
        
        # Verificar aprovações
        self.stdout.write(f'✅ APROVAÇÕES ({aprovacoes.count()} encontradas):')
        if aprovacoes.exists():
            for approval in aprovacoes:
                workorder = approval.work_order
                # Verificar se há log de email
                log_aprovacao = EmailLog.objects.filter(
                    work_order=workorder,
                    tipo_email='aprovacao',
                    criado_em__gte=approval.created_at - timedelta(minutes=5)
                ).first()
                
                status_log = '✓ Log encontrado' if log_aprovacao else '⚠️ SEM LOG'
                status_envio = f'({log_aprovacao.status})' if log_aprovacao else ''
                
                self.stdout.write(
                    f'  - {workorder.codigo} | Aprovado: {approval.aprovado_por.username} | '
                    f'{status_log} {status_envio} | {approval.created_at.strftime("%d/%m/%Y %H:%M")}'
                )
        else:
            self.stdout.write('  Nenhuma aprovação nos últimos 7 dias')
        
        self.stdout.write('')
        
        # Verificar reprovações
        self.stdout.write(f'❌ REPROVAÇÕES ({reprovacoes.count()} encontradas):')
        if reprovacoes.exists():
            for approval in reprovacoes:
                workorder = approval.work_order
                # Verificar se há log de email
                log_reprovacao = EmailLog.objects.filter(
                    work_order=workorder,
                    tipo_email='reprovacao',
                    criado_em__gte=approval.created_at - timedelta(minutes=5)
                ).first()
                
                status_log = '✓ Log encontrado' if log_reprovacao else '⚠️ SEM LOG'
                status_envio = f'({log_reprovacao.status})' if log_reprovacao else ''
                
                self.stdout.write(
                    f'  - {workorder.codigo} | Reprovado: {approval.aprovado_por.username} | '
                    f'{status_log} {status_envio} | {approval.created_at.strftime("%d/%m/%Y %H:%M")}'
                )
        else:
            self.stdout.write('  Nenhuma reprovação nos últimos 7 dias')
        
        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write('')
        self.stdout.write('💡 INTERPRETAÇÃO:')
        self.stdout.write('  - Se aparecer "SEM LOG" = Email pode não ter sido enviado')
        self.stdout.write('  - Se aparecer "Log encontrado (enviado)" = Email foi enviado com sucesso')
        self.stdout.write('  - Se aparecer "Log encontrado (falhou)" = Email falhou ao enviar')
        self.stdout.write('')
        self.stdout.write('⚠️  Se houver "SEM LOG" em aprovações/reprovações recentes,')
        self.stdout.write('   significa que o sistema foi atualizado ANTES dessas ações.')
        self.stdout.write('   Os próximos emails serão logados corretamente.')
