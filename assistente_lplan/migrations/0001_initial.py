from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AssistantQuestionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question", models.TextField(verbose_name="Pergunta")),
                ("context", models.JSONField(blank=True, default=dict, verbose_name="Contexto informado")),
                ("intent", models.CharField(blank=True, max_length=120, verbose_name="Intenção detectada")),
                ("entities", models.JSONField(blank=True, default=dict, verbose_name="Entidades extraídas")),
                ("domain", models.CharField(blank=True, max_length=120, verbose_name="Domínio acionado")),
                ("used_llm", models.BooleanField(default=False, verbose_name="Usou IA na interpretação")),
                ("success", models.BooleanField(default=True, verbose_name="Executou com sucesso")),
                ("error_message", models.TextField(blank=True, verbose_name="Mensagem de erro")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assistant_question_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Log de pergunta do assistente",
                "verbose_name_plural": "Logs de perguntas do assistente",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["user", "-created_at"], name="assistente_l_user_id_42f3a8_idx"),
                    models.Index(fields=["domain", "-created_at"], name="assistente_l_domain_aa2f69_idx"),
                    models.Index(fields=["intent", "-created_at"], name="assistente_l_intent_9a2966_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="AssistantResponseLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("summary", models.CharField(blank=True, max_length=400, verbose_name="Resumo")),
                ("response_payload", models.JSONField(default=dict, verbose_name="Payload estruturado")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "question_log",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="response_log",
                        to="assistente_lplan.assistantquestionlog",
                    ),
                ),
            ],
            options={
                "verbose_name": "Log de resposta do assistente",
                "verbose_name_plural": "Logs de respostas do assistente",
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["-created_at"], name="assistente_l_created_e52318_idx")],
            },
        ),
    ]

