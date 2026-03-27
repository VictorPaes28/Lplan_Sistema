from django.contrib import admin

from .models import (
    AssistantEntityAlias,
    AssistantGuidedRule,
    AssistantLearningFeedback,
    AssistantQuestionLog,
    AssistantResponseLog,
)


@admin.register(AssistantQuestionLog)
class AssistantQuestionLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "intent",
        "domain",
        "used_llm",
        "success",
        "created_at",
    )
    list_filter = ("domain", "intent", "used_llm", "success", "created_at")
    search_fields = ("user__username", "user__first_name", "user__last_name", "question")
    readonly_fields = ("created_at",)


@admin.register(AssistantResponseLog)
class AssistantResponseLogAdmin(admin.ModelAdmin):
    list_display = ("id", "question_log", "summary", "created_at")
    search_fields = ("summary", "question_log__question")
    readonly_fields = ("created_at",)


@admin.register(AssistantLearningFeedback)
class AssistantLearningFeedbackAdmin(admin.ModelAdmin):
    list_display = ("id", "question_log", "user", "helpful", "corrected_intent", "status", "created_at")
    list_filter = ("helpful", "status", "created_at")
    search_fields = ("question_log__question", "note", "corrected_intent", "user__username")
    readonly_fields = ("created_at",)


@admin.register(AssistantGuidedRule)
class AssistantGuidedRuleAdmin(admin.ModelAdmin):
    list_display = ("id", "trigger_text", "intent", "priority", "status", "created_by", "approved_by", "created_at")
    list_filter = ("status", "intent", "created_at")
    search_fields = ("trigger_text", "intent")
    readonly_fields = ("created_at", "approved_at")


@admin.register(AssistantEntityAlias)
class AssistantEntityAliasAdmin(admin.ModelAdmin):
    list_display = ("id", "entity_type", "alias_text", "canonical_value", "status", "created_by", "approved_by")
    list_filter = ("entity_type", "status")
    search_fields = ("alias_text", "canonical_value")
    readonly_fields = ("created_at", "approved_at")
