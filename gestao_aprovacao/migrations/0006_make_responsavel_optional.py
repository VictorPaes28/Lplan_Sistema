# Generated migration to make responsavel field optional

from django.conf import settings
from django.db import migrations, models, connection
import django.db.models.deletion


def remove_fk_and_make_nullable(apps, schema_editor):
    """Remove FK constraint and make column nullable. Django will recreate FK via AlterField."""
    db_engine = schema_editor.connection.vendor
    
    # Para SQLite, não precisa fazer nada - o Django/AlterField já lida com isso
    if db_engine == 'sqlite':
        return
    
    # Para MySQL, fazer a modificação manual
    if db_engine == 'mysql':
        with schema_editor.connection.cursor() as cursor:
            # Descobrir o nome da constraint
            cursor.execute("""
                SELECT CONSTRAINT_NAME 
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'obras_empresa' 
                AND COLUMN_NAME = 'responsavel_id'
                AND REFERENCED_TABLE_NAME IS NOT NULL
                LIMIT 1
            """)
            result = cursor.fetchone()
            
            if result:
                constraint_name = result[0]
                # Remover a constraint
                try:
                    cursor.execute(f"ALTER TABLE obras_empresa DROP FOREIGN KEY {constraint_name};")
                except Exception as e:
                    # Se a constraint não existir, continua
                    pass
            
            # Verificar o tipo exato da coluna auth_user.id para garantir compatibilidade
            cursor.execute("""
                SELECT COLUMN_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'auth_user' 
                AND COLUMN_NAME = 'id'
            """)
            user_id_type = cursor.fetchone()
            
            # Modificar a coluna para permitir NULL, usando o mesmo tipo de auth_user.id
            if user_id_type:
                column_type = user_id_type[0]  # Ex: 'bigint AUTO_INCREMENT' ou 'int(11)'
                # Extrair apenas o tipo base (remover AUTO_INCREMENT se houver)
                base_type = column_type.split()[0] if ' ' in column_type else column_type
                cursor.execute(f"ALTER TABLE obras_empresa MODIFY COLUMN responsavel_id {base_type} NULL;")
            else:
                # Fallback: usar BIGINT
                cursor.execute("ALTER TABLE obras_empresa MODIFY COLUMN responsavel_id BIGINT NULL;")
            
            # NÃO recriar a FK aqui - o AlterField fará isso automaticamente


def reverse_remove_fk_and_make_nullable(apps, schema_editor):
    """Reverter: tornar NOT NULL (FK será recriada pelo AlterField reverso)"""
    db_engine = schema_editor.connection.vendor
    
    # Para SQLite, não precisa fazer nada
    if db_engine == 'sqlite':
        return
    
    # Para MySQL
    if db_engine == 'mysql':
        with schema_editor.connection.cursor() as cursor:
            # Verificar o tipo de auth_user.id
            cursor.execute("""
                SELECT COLUMN_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'auth_user' 
                AND COLUMN_NAME = 'id'
            """)
            user_id_type = cursor.fetchone()
            
            # Tornar NOT NULL
            if user_id_type:
                base_type = user_id_type[0].split()[0] if ' ' in user_id_type[0] else user_id_type[0]
                cursor.execute(f"ALTER TABLE obras_empresa MODIFY COLUMN responsavel_id {base_type} NOT NULL;")
            else:
                cursor.execute("ALTER TABLE obras_empresa MODIFY COLUMN responsavel_id BIGINT NOT NULL;")


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('gestao_aprovacao', '0005_make_empresa_required'),
    ]

    operations = [
        # Passo 1-3: Remover FK, tornar nullable, recriar FK
        migrations.RunPython(
            code=remove_fk_and_make_nullable,
            reverse_code=reverse_remove_fk_and_make_nullable,
        ),
        # Passo 4: Atualizar o modelo Django
        migrations.AlterField(
            model_name='empresa',
            name='responsavel',
            field=models.ForeignKey(
                blank=True,
                help_text='Usuário responsável por gerenciar esta empresa',
                limit_choices_to={'groups__name': 'Responsavel Empresa'},
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='empresas_responsavel',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Responsável pela Empresa'
            ),
        ),
    ]

