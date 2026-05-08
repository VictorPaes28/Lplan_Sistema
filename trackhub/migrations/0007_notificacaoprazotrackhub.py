from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("trackhub", "0006_remove_etapapendencia_responsavel_externo"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificacaoPrazoTrackHub",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("alvo_tipo", models.CharField(choices=[("pendencia", "Pendência"), ("etapa", "Etapa")], max_length=20)),
                ("alvo_id", models.PositiveIntegerField()),
                ("janela_horas", models.PositiveIntegerField()),
                ("referencia_prazo", models.DateTimeField()),
                ("enviado_em", models.DateTimeField(auto_now_add=True)),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="trackhub_notificacoes_prazo", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Lembrete de prazo TrackHub",
                "verbose_name_plural": "Lembretes de prazo TrackHub",
                "ordering": ["-enviado_em"],
                "unique_together": {("alvo_tipo", "alvo_id", "usuario", "janela_horas", "referencia_prazo")},
            },
        ),
    ]

