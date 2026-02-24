"""
Comando de gerenciamento para criar os grupos de usuários padrão.
Execute: python manage.py create_groups
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from obras.models import WorkOrder, Empresa, Obra, WorkOrderPermission, UserEmpresa


class Command(BaseCommand):
    help = 'Cria os grupos de usuários padrão (Solicitante, Aprovador, Responsavel Empresa, Administrador)'

    def handle(self, *args, **options):
        # Criar grupos
        grupos = {
            'Solicitante': {
                'description': 'Solicitantes podem criar e gerenciar seus próprios pedidos de obra',
                'permissions': {
                    'workorder': ['add_workorder', 'view_workorder', 'change_workorder'],
                }
            },
            'Aprovador': {
                'description': 'Aprovadores podem aprovar/reprovar pedidos de obra',
                'permissions': {
                    'workorder': ['add_workorder', 'view_workorder', 'change_workorder', 'delete_workorder'],
                }
            },
            'Responsavel Empresa': {
                'description': 'Responsáveis pela empresa podem gerenciar usuários e permissões das obras da empresa',
                'permissions': {
                    'empresa': ['add_empresa', 'change_empresa', 'view_empresa'],
                    'obra': ['add_obra', 'change_obra', 'view_obra', 'delete_obra'],
                    'workorderpermission': ['add_workorderpermission', 'change_workorderpermission', 'view_workorderpermission', 'delete_workorderpermission'],
                    'userempresa': ['add_userempresa', 'change_userempresa', 'view_userempresa', 'delete_userempresa'],
                    'workorder': ['view_workorder'],
                }
            },
            'Administrador': {
                'description': 'Administradores têm acesso total ao sistema',
                'permissions': {
                    'empresa': ['add_empresa', 'change_empresa', 'delete_empresa', 'view_empresa'],
                    'obra': ['add_obra', 'change_obra', 'delete_obra', 'view_obra'],
                    'workorder': ['add_workorder', 'change_workorder', 'delete_workorder', 'view_workorder'],
                    'workorderpermission': ['add_workorderpermission', 'change_workorderpermission', 'delete_workorderpermission', 'view_workorderpermission'],
                    'userempresa': ['add_userempresa', 'change_userempresa', 'delete_userempresa', 'view_userempresa'],
                }
            }
        }
        
        # Obter ContentTypes
        content_types = {
            'workorder': ContentType.objects.get_for_model(WorkOrder),
            'empresa': ContentType.objects.get_for_model(Empresa),
            'obra': ContentType.objects.get_for_model(Obra),
            'workorderpermission': ContentType.objects.get_for_model(WorkOrderPermission),
            'userempresa': ContentType.objects.get_for_model(UserEmpresa),
        }
        
        for nome_grupo, config in grupos.items():
            grupo, created = Group.objects.get_or_create(name=nome_grupo)
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Grupo "{nome_grupo}" criado com sucesso!')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Grupo "{nome_grupo}" já existe. Atualizando permissões...')
                )
            
            # Limpar permissões existentes do grupo
            grupo.permissions.clear()
            
            # Adicionar permissões por modelo
            for model_name, codenames in config['permissions'].items():
                if model_name in content_types:
                    ct = content_types[model_name]
                    for codename in codenames:
                        try:
                            perm = Permission.objects.get(
                                content_type=ct,
                                codename=codename
                            )
                            grupo.permissions.add(perm)
                            self.stdout.write(f'  ✓ Permissão "{codename}" ({model_name}) adicionada')
                        except Permission.DoesNotExist:
                            self.stdout.write(
                                self.style.WARNING(f'  ⚠ Permissão "{codename}" ({model_name}) não encontrada')
                            )
        
        self.stdout.write(
            self.style.SUCCESS('\n✓ Grupos criados/atualizados com sucesso!')
        )
        self.stdout.write('\nPara atribuir um usuário a um grupo, use o Django Admin ou:')
        self.stdout.write('  from django.contrib.auth.models import User, Group')
        self.stdout.write('  user = User.objects.get(username="usuario")')
        self.stdout.write('  grupo = Group.objects.get(name="Solicitante")')
        self.stdout.write('  user.groups.add(grupo)')

