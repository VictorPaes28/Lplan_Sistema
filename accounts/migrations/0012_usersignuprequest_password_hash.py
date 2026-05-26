from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_usersignuprequest_phone'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersignuprequest',
            name='password_hash',
            field=models.CharField(blank=True, max_length=128, verbose_name='Senha (hash)'),
        ),
    ]
