# researcher_app/admin.py

from django.contrib import admin
from .models import (
    UploadedPDF, ExtractedContent, BlogOutline,
    BlogDraft, ChatMessage, NormalizationRule
)


@admin.register(UploadedPDF)
class UploadedPDFAdmin(admin.ModelAdmin):
    list_display = ('id', 'file', 'uploaded_at')
    search_fields = ('file',)
    list_filter = ('uploaded_at',)


@admin.register(ExtractedContent)
class ExtractedContentAdmin(admin.ModelAdmin):
    list_display = ('id', 'pdf', 'created_at')
    search_fields = ('pdf__file',)
    list_filter = ('created_at',)


@admin.register(BlogOutline)
class BlogOutlineAdmin(admin.ModelAdmin):
    list_display = ('id', 'pdf', 'status', 'created_at')
    list_filter  = ('status',)

@admin.register(BlogDraft)
class BlogDraftAdmin(admin.ModelAdmin):
    list_display = ('outline', 'section_order', 'section_title', 'is_final', 'last_updated')
    list_filter  = ('is_final',)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'pdf', 'timestamp')
    search_fields = ('pdf__file', 'user_message', 'agent_response')
    list_filter = ('timestamp',)


@admin.register(NormalizationRule)
class NormalizationRuleAdmin(admin.ModelAdmin):
    list_display = ('id', 'rule_name', 'pattern', 'replacement', 'created_at')
    search_fields = ('rule_name', 'pattern')
    list_filter = ('created_at',)
