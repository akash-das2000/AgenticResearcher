from django.urls import path
from .views import (
    UploadPDFView, ExtractPDFView, GenerateOutlineView,
    DraftSectionView, FormatBlogView, ChatWithPDFView,
    NormalizationRuleView
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # API endpoints (these are under /api/ in project urls.py)
    path('upload/', UploadPDFView.as_view(), name='upload-pdf'),
    path('extract/<int:pk>/', ExtractPDFView.as_view(), name='extract-pdf'),
    path('outline/<int:pk>/', GenerateOutlineView.as_view(), name='generate-outline'),
    path('write/<int:pk>/', DraftSectionView.as_view(), name='draft-section'),
    path('format/<int:pk>/', FormatBlogView.as_view(), name='format-blog'),
    path('chat/<int:pk>/', ChatWithPDFView.as_view(), name='chat-with-pdf'),
    path('rules/', NormalizationRuleView.as_view(), name='normalization-rules'),
]

# Serve media files
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
