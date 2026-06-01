from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_usersignuprequest_password_hash'),
        ('workflow_aprovacao', '0011_externalparticipantsignuprequest_created_linked_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='externalparticipantsignuprequest',
            name='central_signup_request',
            field=models.OneToOneField(
                blank=True,
                help_text='Espelho na Central de Cadastros (/central/cadastros/).',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='workflow_external_signup',
                to='accounts.usersignuprequest',
            ),
        ),
    ]
