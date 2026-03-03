"""
Comando UNIFICADO para criar todos os grupos do Sistema LPLAN.

Executa: python manage.py setup_groups

Este comando substitui os antigos:
  - accounts/management/commands/seed_grupos.py (Mapa de Suprimentos)
  - gestao_aprovacao/management/commands/create_groups.py (Solicitante, Aprovador, etc.)

Mapa de Roles:
  ┌─────────────────────────────────────────────────────────────────┐
  │  GRUPO              │ SISTEMA         │ FUNCAO                  │
  ├─────────────────────┼─────────────────┼─────────────────────────┤
  │  Administrador      │ Gestao Aprov.   │ Acesso total gestao     │
  │  Responsavel Empresa│ Gestao Aprov.   │ Gerencia empresa/obras  │
  │  Aprovador          │ Gestao Aprov.   │ Aprova/rejeita pedidos  │
  │  Solicitante        │ Gestao Aprov.   │ Cria pedidos de obra    │
  │  Diário de Obra     │ Diario de Obra  │ Aprova diarios de obra  │
  │  Mapa de Suprimentos│ Mapa Controle   │ Acesso completo (mapa   │
  │                     │                 │ + dashboard + import)   │
  └─────────────────────┴─────────────────┴─────────────────────────┘
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


GRUPOS_CONFIG = {
    # =====================================================
    # GESTAO DE APROVACAO (GestControll)
    # =====================================================
    'Administrador': {
        'sistema': 'Gestao de Aprovacao',
        'descricao': 'Acesso total ao modulo de gestao. Gerencia usuarios, empresas, obras e pedidos.',
        'permissions': {
            'gestao_aprovacao': {
                'empresa': ['add', 'change', 'delete', 'view'],
                'obra': ['add', 'change', 'delete', 'view'],
                'workorder': ['add', 'change', 'delete', 'view'],
                'workorderpermission': ['add', 'change', 'delete', 'view'],
                'userempresa': ['add', 'change', 'delete', 'view'],
            }
        }
    },
    'Responsavel Empresa': {
        'sistema': 'Gestao de Aprovacao',
        'descricao': 'Gerencia usuarios e permissoes das obras da sua empresa.',
        'permissions': {
            'gestao_aprovacao': {
                'empresa': ['add', 'change', 'view'],
                'obra': ['add', 'change', 'view', 'delete'],
                'workorderpermission': ['add', 'change', 'view', 'delete'],
                'userempresa': ['add', 'change', 'view', 'delete'],
                'workorder': ['view'],
            }
        }
    },
    'Aprovador': {
        'sistema': 'Gestao de Aprovacao',
        'descricao': 'Aprova ou rejeita pedidos de obra. Ve pedidos das obras da sua empresa.',
        'permissions': {
            'gestao_aprovacao': {
                'workorder': ['add', 'view', 'change', 'delete'],
            }
        }
    },
    'Solicitante': {
        'sistema': 'Gestao de Aprovacao',
        'descricao': 'Cria e gerencia seus proprios pedidos de obra.',
        'permissions': {
            'gestao_aprovacao': {
                'workorder': ['add', 'view', 'change'],
            }
        }
    },

    # =====================================================
    # DIARIO DE OBRA (Core)
    # =====================================================
    'Diário de Obra': {
        'sistema': 'Diario de Obra',
        'descricao': 'Aprova ou rejeita diarios de obra. Acesso a relatorios gerenciais.',
        'permissions': {
            'core': {
                'constructiondiary': ['add', 'view', 'change'],
            }
        }
    },

    # =====================================================
    # MAPA DE CONTROLE (Suprimentos/Engenharia)
    # =====================================================
    'Mapa de Suprimentos': {
        'sistema': 'Mapa de Suprimentos',
        'descricao': 'Acesso completo: mapa de suprimentos, dashboard, importacao Sienge.',
        'permissions': {}
    },
}


class Command(BaseCommand):
    help = 'Cria TODOS os grupos de usuarios do Sistema LPLAN unificado'

    def add_arguments(self, parser):
        parser.add_argument(
            '--list',
            action='store_true',
            help='Apenas lista os grupos e suas descricoes, sem criar',
        )

    def handle(self, *args, **options):
        if options['list']:
            self._list_groups()
            return

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Setup de Grupos - Sistema LPLAN ===\n'))

        created_count = 0
        updated_count = 0

        for nome_grupo, config in GRUPOS_CONFIG.items():
            grupo, created = Group.objects.get_or_create(name=nome_grupo)

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  + Grupo "{nome_grupo}" criado [{config["sistema"]}]')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'  ~ Grupo "{nome_grupo}" ja existe [{config["sistema"]}]')
                )

            # Atribuir permissoes
            perms_added = 0
            grupo.permissions.clear()

            for app_label, models in config.get('permissions', {}).items():
                for model_name, actions in models.items():
                    for action in actions:
                        codename = f'{action}_{model_name}'
                        try:
                            perm = Permission.objects.get(
                                content_type__app_label=app_label,
                                codename=codename
                            )
                            grupo.permissions.add(perm)
                            perms_added += 1
                        except Permission.DoesNotExist:
                            self.stdout.write(
                                self.style.NOTICE(f'    ? Permissao "{codename}" ({app_label}) nao encontrada')
                            )

            if perms_added > 0:
                self.stdout.write(f'    {perms_added} permissoes atribuidas')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Resultado: {created_count} criados, {updated_count} ja existiam'
        ))
        self.stdout.write(self.style.SUCCESS('Setup de grupos concluido!\n'))

    def _list_groups(self):
        """Lista todos os grupos configurados."""
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Grupos do Sistema LPLAN ===\n'))

        current_sistema = None
        for nome, config in GRUPOS_CONFIG.items():
            if config['sistema'] != current_sistema:
                current_sistema = config['sistema']
                self.stdout.write(self.style.HTTP_INFO(f'\n  [{current_sistema}]'))

            exists = Group.objects.filter(name=nome).exists()
            status = self.style.SUCCESS('OK') if exists else self.style.ERROR('NAO CRIADO')

            self.stdout.write(f'    {nome}: {config["descricao"]} [{status}]')

        # Mostrar grupos que existem no DB mas nao estao no config
        db_groups = set(Group.objects.values_list('name', flat=True))
        config_groups = set(GRUPOS_CONFIG.keys())
        extra = db_groups - config_groups

        if extra:
            self.stdout.write(self.style.WARNING(f'\n  [Grupos extras no banco (nao configurados)]:'))
            for nome in sorted(extra):
                self.stdout.write(self.style.WARNING(f'    {nome}'))

        self.stdout.write('')
