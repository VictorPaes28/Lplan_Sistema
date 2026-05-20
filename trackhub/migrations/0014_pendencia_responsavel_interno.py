from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("trackhub", "0013_tipocustom_utf8mb4"),
    ]

    operations = [
        migrations.AddField(
            model_name="pendencia",
            name="responsavel_interno",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pendencias_responsavel",
                to="auth.user",
            ),
        ),
    ]
