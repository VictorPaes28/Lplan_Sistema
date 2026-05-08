from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestao_aprovacao", "0027_obra_sigla"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="telefone",
            field=models.CharField(
                blank=True,
                help_text="Telefone de contato do usuário (opcional)",
                max_length=20,
                verbose_name="Telefone",
            ),
        ),
    ]

