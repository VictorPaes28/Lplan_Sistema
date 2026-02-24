# Generated manually for refactoring to Empresa and WorkOrderPermission system

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def create_empresa_padrao_and_migrate(apps, schema_editor):
    """
    Função no-op: não cria empresa padrão nem migra dados.
    As empresas devem ser criadas manualmente pelo admin.
    """
    # Não fazer nada - empresas serão criadas manualmente
    pass


def remove_unique_constraint_codigo(apps, schema_editor):
    """
    Remove a constraint unique do código da obra se existir.
    Adaptado para MySQL e SQLite.
    """
    db_engine = schema_editor.connection.vendor
    
    if db_engine == 'mysql':
        # Para MySQL
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("""
                SET @exist := (SELECT COUNT(*) FROM information_schema.statistics 
                               WHERE table_schema = DATABASE() 
                               AND table_name = 'obras_obra' 
                               AND index_name = 'obras_obra_codigo_unique');
                SET @sqlstmt := IF(@exist > 0, 'ALTER TABLE obras_obra DROP INDEX obras_obra_codigo_unique', 'SELECT 1');
                PREPARE stmt FROM @sqlstmt;
                EXECUTE stmt;
                DEALLOCATE PREPARE stmt;
            """)
    elif db_engine == 'sqlite':
        # Para SQLite, tenta remover o índice se existir
        with schema_editor.connection.cursor() as cursor:
            try:
                cursor.execute("DROP INDEX IF EXISTS obras_obra_codigo_unique")
            except Exception:
                # Se não existir, ignora o erro
                pass
    # Para outros bancos, não faz nada


def reverse_remove_unique_constraint_codigo(apps, schema_editor):
    """Função reversa - não faz nada"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('obras', '0003_make_fields_required'),
    ]

    operations = [
        # Criar modelo Empresa
        migrations.CreateModel(
            name='Empresa',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(help_text='Código único da empresa (ex: EMP-001)', max_length=50, unique=True, verbose_name='Código')),
                ('nome', models.CharField(help_text='Nome da empresa', max_length=200, verbose_name='Nome')),
                ('razao_social', models.CharField(blank=True, help_text='Razão social completa (opcional)', max_length=300, null=True, verbose_name='Razão Social')),
                ('cnpj', models.CharField(blank=True, help_text='CNPJ da empresa (opcional)', max_length=18, null=True, verbose_name='CNPJ')),
                ('email', models.EmailField(blank=True, help_text='E-mail principal da empresa (opcional)', max_length=254, null=True, verbose_name='E-mail')),
                ('telefone', models.CharField(blank=True, help_text='Telefone de contato (opcional)', max_length=20, null=True, verbose_name='Telefone')),
                ('ativo', models.BooleanField(default=True, help_text='Indica se a empresa está ativa', verbose_name='Ativa')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
                ('responsavel', models.ForeignKey(help_text='Usuário responsável por esta empresa', on_delete=django.db.models.deletion.PROTECT, related_name='empresas_responsavel', to=settings.AUTH_USER_MODEL, verbose_name='Responsável')),
            ],
            options={
                'verbose_name': 'Empresa',
                'verbose_name_plural': 'Empresas',
                'ordering': ['codigo'],
            },
        ),
        
        # Criar modelo UserEmpresa
        migrations.CreateModel(
            name='UserEmpresa',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ativo', models.BooleanField(default=True, help_text='Indica se o vínculo está ativo', verbose_name='Ativo')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('empresa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usuarios_vinculados', to='obras.empresa', verbose_name='Empresa')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='empresas_vinculadas', to=settings.AUTH_USER_MODEL, verbose_name='Usuário')),
            ],
            options={
                'verbose_name': 'Vínculo Usuário-Empresa',
                'verbose_name_plural': 'Vínculos Usuário-Empresa',
                'unique_together': {('usuario', 'empresa')},
            },
        ),
        
        # Criar modelo WorkOrderPermission
        migrations.CreateModel(
            name='WorkOrderPermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo_permissao', models.CharField(choices=[('solicitante', 'Solicitante'), ('aprovador', 'Aprovador')], help_text='Tipo de permissão: Solicitante ou Aprovador', max_length=20, verbose_name='Tipo de Permissão')),
                ('ativo', models.BooleanField(default=True, help_text='Indica se a permissão está ativa', verbose_name='Ativa')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('obra', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='permissoes', to='obras.obra', verbose_name='Obra')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='permissoes_obra', to=settings.AUTH_USER_MODEL, verbose_name='Usuário')),
            ],
            options={
                'verbose_name': 'Permissão de Pedido',
                'verbose_name_plural': 'Permissões de Pedidos',
                'unique_together': {('obra', 'usuario', 'tipo_permissao')},
            },
        ),
        
        # Adicionar campo empresa ao modelo Obra (temporariamente nullable)
        migrations.AddField(
            model_name='obra',
            name='empresa',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='obras',
                to='obras.empresa',
                verbose_name='Empresa',
                help_text='Empresa à qual esta obra pertence'
            ),
        ),
        
        # Remover unique constraint do código da obra se existir
        # (será único por empresa, mas isso será adicionado depois quando empresa for obrigatória)
        # Usa RunPython para detectar o tipo de banco e executar SQL apropriado
        migrations.RunPython(
            code=remove_unique_constraint_codigo,
            reverse_code=reverse_remove_unique_constraint_codigo,
        ),
        
        # Adicionar índices
        migrations.AddIndex(
            model_name='empresa',
            index=models.Index(fields=['codigo'], name='obras_empre_codigo_idx'),
        ),
        migrations.AddIndex(
            model_name='empresa',
            index=models.Index(fields=['nome'], name='obras_empre_nome_idx'),
        ),
        migrations.AddIndex(
            model_name='workorderpermission',
            index=models.Index(fields=['obra', 'usuario'], name='obras_worko_obra_id_usuari_idx'),
        ),
        migrations.AddIndex(
            model_name='workorderpermission',
            index=models.Index(fields=['tipo_permissao', 'ativo'], name='obras_worko_tipo_pe_ativ_idx'),
        ),
        
        # Criar empresa padrão e migrar dados (RunPython) - REMOVIDO
        # Não cria empresa padrão automaticamente. Empresas devem ser criadas manualmente.
        migrations.RunPython(
            code=lambda apps, schema_editor: create_empresa_padrao_and_migrate(apps, schema_editor),
            reverse_code=migrations.RunPython.noop,
        ),
        
        # NOTA: O campo empresa permanece nullable temporariamente.
        # Após criar empresas manualmente e vincular obras, você pode criar uma migração
        # adicional para tornar o campo obrigatório se necessário.
        
        # Adicionar unique_together para código por empresa (apenas quando empresa estiver definida)
        # Como empresa pode ser NULL, não podemos usar unique_together ainda.
        # Isso será tratado no nível da aplicação ou em migração futura.
        
        # Remover campos ManyToMany antigos (se existirem)
        # SQL compatível com MySQL e SQLite
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS obras_obra_engenheiros; DROP TABLE IF EXISTS obras_obra_gestores;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]

