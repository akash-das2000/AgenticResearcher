# researcher_app/serializers.py

from rest_framework import serializers
from .models import UploadedPDF, ExtractedContent, BlogOutline, BlogDraft, ChatMessage, NormalizationRule


class UploadedPDFSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedPDF
        fields = '__all__'


class ExtractedContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtractedContent
        fields = '__all__'


class BlogOutlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogOutline
        fields = '__all__'


class BlogDraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogDraft
        fields = '__all__'


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = '__all__'


class NormalizationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = NormalizationRule
        fields = '__all__'
