from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recursos_humanos', '0008_colaborador_gestor_aprovador_user_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='colaborador',
            name='email',
            field=models.EmailField(blank=True, max_length=254, verbose_name='E-mail'),
        ),
        migrations.AddField(
            model_name='colaborador',
            name='telefone',
            field=models.CharField(blank=True, max_length=20, verbose_name='Telefone'),
        ),
    ]
