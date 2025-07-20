# researcher_app/models.py

from django.db import models
from django.conf import settings


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
    Stores generated blog outlines linked to an UploadedPDF,
    plus metadata (title & author) once the user finalizes.
    """
    pdf = models.ForeignKey(
        UploadedPDF,
        on_delete=models.CASCADE,
        related_name='outlines'
    )
    title = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text="Final blog title"
    )
    author_name = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Author name for the blog"
    )
    outline_json = models.JSONField()
    STATUS_CHOICES = [
        ('drafting',   'Editing Outline'),
        ('finalized',  'Outline Finalized'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='drafting',
        help_text="Have we locked in the outline yet?"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"Outline #{self.id} for {self.pdf.file.name} "
            f"({self.get_status_display()})"
        )


class BlogDraft(models.Model):
    """
    Stores drafted blog sections linked to a BlogOutline.
    """
    outline = models.ForeignKey(BlogOutline, on_delete=models.CASCADE, related_name='drafts')
    section_order = models.PositiveIntegerField(help_text="Order of this section within the outline")
    section_title = models.CharField(max_length=255)
    content = models.TextField(help_text="Current draft of the section")
    is_final = models.BooleanField(default=False,
                                   help_text="True once the user has ‘OK’d’ this section")
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['section_order']

    def __str__(self):
        status = "Final" if self.is_final else "In progress"
        return f"[{self.section_order}] {self.section_title} ({status})"

class Feedback(models.Model):
    """
    Records every user tweak request on an outline or section.
    """
    outline = models.ForeignKey(
        BlogOutline,
        on_delete=models.CASCADE,
        related_name="feedbacks"
    )
    section_order = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Which section this feedback applies to (or null for outline)"
    )
    text = models.TextField(help_text="What the user asked to tweak")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        loc = f"Section {self.section_order}" if self.section_order is not None else "Outline"
        return f"[{loc}] {self.text[:30]}…"


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
