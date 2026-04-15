from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0006_usersignuprequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='userloginlog',
            name='ip_address',
            field=models.GenericIPAddressField(
                blank=True,
                null=True,
                verbose_name='IP',
            ),
        ),
        migrations.AddField(
            model_name='userloginlog',
            name='user_agent',
            field=models.CharField(blank=True, max_length=256, verbose_name='User-Agent'),
        ),
    ]
