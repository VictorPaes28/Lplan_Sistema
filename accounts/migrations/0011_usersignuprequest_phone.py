from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_gestcontroll_enviar_central_group'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersignuprequest',
            name='phone',
            field=models.CharField(blank=True, max_length=32, verbose_name='Telefone'),
        ),
    ]
