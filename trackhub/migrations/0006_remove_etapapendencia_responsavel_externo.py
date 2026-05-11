# Generated manually for TrackHub — remove responsável externo

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("trackhub", "0005_atividade_pendencia"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="etapapendencia",
            name="responsavel_externo_email",
        ),
        migrations.RemoveField(
            model_name="etapapendencia",
            name="responsavel_externo_nome",
        ),
        migrations.RemoveField(
            model_name="etapapendencia",
            name="responsavel_externo_whatsapp",
        ),
    ]
