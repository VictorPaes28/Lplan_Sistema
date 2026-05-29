from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workflow_aprovacao', '0010_approvalprocessattachment'),
    ]

    operations = [
        migrations.AddField(
            model_name='externalparticipantsignuprequest',
            name='created_linked_user',
            field=models.BooleanField(
                default=False,
                help_text='True quando a aprovação criou um novo usuário (senha padrão gerada).',
            ),
        ),
    ]
