# Generated - e-mails que recebem o diário da obra todo dia

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_add_project_member'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectDiaryRecipient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254, verbose_name='E-mail')),
                ('nome', models.CharField(blank=True, help_text='Ex.: Gerente, Fiscal da obra', max_length=120, verbose_name='Nome (opcional)')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='diary_recipients', to='core.project', verbose_name='Obra')),
            ],
            options={
                'verbose_name': 'E-mail para envio do diário',
                'verbose_name_plural': 'E-mails para envio do diário',
                'ordering': ['email'],
                'unique_together': {('project', 'email')},
            },
        ),
    ]
