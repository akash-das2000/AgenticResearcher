# researcher_app/models.py

from django.db import models


class UploadedPDF(models.Model):
    """
    Stores uploaded PDF files.
    """
    file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name


class ExtractedContent(models.Model):
    """
    Stores extracted text, images, and tables for each PDF.
    """
    pdf = models.OneToOneField(UploadedPDF, on_delete=models.CASCADE, related_name='content')
    text = models.TextField()
    images = models.JSONField(default=list)  # list of image paths/URLs
    tables = models.JSONField(default=list)  # list of table paths/URLs
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Extracted content for {self.pdf.file.name}"


class BlogOutline(models.Model):
    """
    Stores generated blog outlines linked to an UploadedPDF.
    """
    pdf = models.ForeignKey(UploadedPDF, on_delete=models.CASCADE, related_name='outlines')
    outline_json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Outline for {self.pdf.file.name}"


class BlogDraft(models.Model):
    """
    Stores drafted blog sections linked to a BlogOutline.
    """
    outline = models.ForeignKey(BlogOutline, on_delete=models.CASCADE, related_name='drafts')
    section_title = models.CharField(max_length=255)
    content = models.TextField()
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Draft: {self.section_title} (Outline: {self.outline.id})"


class ChatMessage(models.Model):
    """
    Stores chat history for each PDF.
    """
    pdf = models.ForeignKey(UploadedPDF, on_delete=models.CASCADE, related_name='chats')
    user_message = models.TextField()
    agent_response = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat on {self.pdf.file.name} at {self.timestamp}"


class NormalizationRule(models.Model):
    """
    Stores normalization rules for text cleaning.
    """
    rule_name = models.CharField(max_length=255)
    pattern = models.CharField(max_length=500)
    replacement = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.rule_name
