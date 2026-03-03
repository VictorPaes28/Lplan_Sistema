"""
Management command para enviar lembretes periódicos sobre pedidos pendentes.
Executar diariamente via cron job ou agendador de tarefas.

Uso:
    python manage.py enviar_lembretes
    python manage.py enviar_lembretes --dias 3,5,7,10,15
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from obras.models import WorkOrder, WorkOrderPermission, Empresa, Lembrete, Notificacao
from obras.utils import criar_notificacao
from obras.email_utils import enviar_email_novo_pedido


class Command(BaseCommand):
    help = 'Envia lembretes para aprovadores sobre pedidos pendentes há X dias'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=str,
            default='1,2,3,5,7,10,15,20,30',
            help='Dias para verificar pedidos pendentes (separados por vírgula). Ex: 1,2,3,5,7,10,15,20,30'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas simula o envio, não envia realmente'
        )

    def handle(self, *args, **options):
        dias_str = options['dias']
        dry_run = options['dry_run']
        
        # Converter string de dias para lista de inteiros
        try:
            dias_lista = [int(d.strip()) for d in dias_str.split(',') if d.strip()]
        except ValueError:
            self.stdout.write(self.style.ERROR('Erro: Dias devem ser números separados por vírgula. Ex: 3,5,7,10,15'))
            return
        
        if not dias_lista:
            self.stdout.write(self.style.ERROR('Erro: Nenhum dia especificado.'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Verificando pedidos pendentes há {dias_lista} dias...'))
        self.stdout.write(self.style.SUCCESS(f'Lembretes configurados para: {", ".join([str(d) + " dias" for d in dias_lista])}'))
        
        agora = timezone.now()
        total_lembretes = 0
        
        # Para cada dia configurado
        for dias in dias_lista:
            # Calcular data limite (pedidos enviados há X dias)
            data_limite = agora - timedelta(days=dias)
            
            # Buscar pedidos pendentes ou em reaprovação enviados há exatamente X dias (com margem de 12 horas)
            # Margem menor para lembretes mais frequentes
            data_inicio = data_limite - timedelta(hours=12)
            data_fim = data_limite + timedelta(hours=12)
            
            pedidos_pendentes = WorkOrder.objects.filter(
                status__in=['pendente', 'reaprovacao'],
                data_envio__gte=data_inicio,
                data_envio__lte=data_fim
            ).select_related('obra', 'obra__empresa', 'criado_por')
            
            self.stdout.write(f'\nVerificando pedidos pendentes há {dias} dias...')
            self.stdout.write(f'Encontrados {pedidos_pendentes.count()} pedidos.')
            
            # Para cada pedido pendente
            for pedido in pedidos_pendentes:
                # Calcular dias exatos pendentes
                dias_pendentes_exatos = (agora - pedido.data_envio).days
                
                # Verificar se está dentro da faixa do dia configurado (±0.5 dia de tolerância para lembretes mais frequentes)
                # Para dias <= 3, tolerância menor; para dias > 3, tolerância maior
                tolerancia = 0.5 if dias <= 3 else 1.0
                if abs(dias_pendentes_exatos - dias) > tolerancia:
                    continue
                
                # Buscar aprovadores da empresa da obra
                empresa = pedido.obra.empresa
                
                # Buscar aprovadores com permissão em QUALQUER obra da mesma empresa
                obras_empresa = empresa.obras.filter(ativo=True)
                
                aprovadores = set()
                
                # Buscar aprovadores via WorkOrderPermission
                permissoes = WorkOrderPermission.objects.filter(
                    obra__in=obras_empresa,
                    tipo_permissao='aprovador',
                    ativo=True
                ).select_related('usuario', 'obra')
                
                for perm in permissoes:
                    if perm.usuario.is_active:
                        aprovadores.add(perm.usuario)
                
                # Também buscar admins
                from django.contrib.auth.models import User, Group
                try:
                    grupo_admin = Group.objects.get(name='Administrador')
                    admins = User.objects.filter(
                        groups=grupo_admin,
                        is_active=True
                    )
                    for admin_user in admins:
                        aprovadores.add(admin_user)
                except Group.DoesNotExist:
                    pass
                
                # Determinar tipo de lembrete baseado nos dias exatos
                tipo_lembrete = None
                if dias_pendentes_exatos == 1:
                    tipo_lembrete = 'pendente_1_dia'
                elif dias_pendentes_exatos == 2:
                    tipo_lembrete = 'pendente_2_dias'
                elif dias_pendentes_exatos == 3:
                    tipo_lembrete = 'pendente_3_dias'
                elif dias_pendentes_exatos == 5:
                    tipo_lembrete = 'pendente_5_dias'
                elif dias_pendentes_exatos == 7:
                    tipo_lembrete = 'pendente_7_dias'
                elif dias_pendentes_exatos == 10:
                    tipo_lembrete = 'pendente_10_dias'
                elif dias_pendentes_exatos == 15:
                    tipo_lembrete = 'pendente_15_dias'
                elif dias_pendentes_exatos == 20:
                    tipo_lembrete = 'pendente_20_dias'
                elif dias_pendentes_exatos == 30:
                    tipo_lembrete = 'pendente_30_dias'
                else:
                    # Para dias não configurados, usar o mais próximo
                    if dias_pendentes_exatos <= 2:
                        tipo_lembrete = 'pendente_2_dias'
                    elif dias_pendentes_exatos <= 3:
                        tipo_lembrete = 'pendente_3_dias'
                    elif dias_pendentes_exatos <= 5:
                        tipo_lembrete = 'pendente_5_dias'
                    elif dias_pendentes_exatos <= 7:
                        tipo_lembrete = 'pendente_7_dias'
                    elif dias_pendentes_exatos <= 10:
                        tipo_lembrete = 'pendente_10_dias'
                    elif dias_pendentes_exatos <= 15:
                        tipo_lembrete = 'pendente_15_dias'
                    elif dias_pendentes_exatos <= 20:
                        tipo_lembrete = 'pendente_20_dias'
                    else:
                        tipo_lembrete = 'pendente_30_dias'
                
                # Para cada aprovador
                for aprovador in aprovadores:
                    # Verificar se já foi enviado lembrete hoje deste tipo para este pedido
                    hoje = agora.date()
                    lembrete_existente = Lembrete.objects.filter(
                        work_order=pedido,
                        enviado_para=aprovador,
                        tipo=tipo_lembrete,
                        enviado_em__date=hoje
                    ).exists()
                    
                    if lembrete_existente:
                        continue  # Já foi enviado hoje
                    
                    if dry_run:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  [DRY-RUN] Enviaria lembrete para {aprovador.username} '
                                f'sobre pedido {pedido.codigo} (pendente há {dias_pendentes_exatos} dias)'
                            )
                        )
                    else:
                        # Criar registro de lembrete
                        Lembrete.objects.create(
                            work_order=pedido,
                            enviado_para=aprovador,
                            tipo=tipo_lembrete,
                            dias_pendente=dias_pendentes_exatos
                        )
                        
                        # Criar notificação in-app
                        criar_notificacao(
                            usuario=aprovador,
                            tipo='pedido_atualizado',
                            titulo=f'Lembrete: Pedido {pedido.codigo} pendente há {dias_pendentes_exatos} dias',
                            mensagem=f'O pedido {pedido.codigo} ({pedido.nome_credor}) está aguardando sua aprovação há {dias_pendentes_exatos} dias. Por favor, revise e tome uma decisão.',
                            work_order=pedido
                        )
                        
                        # Opcional: Enviar email (descomentar se quiser)
                        # try:
                        #     enviar_email_lembrete(pedido, aprovador, dias_pendentes_exatos)
                        # except Exception as e:
                        #     self.stdout.write(self.style.ERROR(f'Erro ao enviar email para {aprovador.email}: {e}'))
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  ✓ Lembrete enviado para {aprovador.username} '
                                f'sobre pedido {pedido.codigo} (pendente há {dias_pendentes_exatos} dias)'
                            )
                        )
                    
                    total_lembretes += 1
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\n[DRY-RUN] Total de lembretes que seriam enviados: {total_lembretes}'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Processo concluído! Total de lembretes enviados: {total_lembretes}'
                )
            )

