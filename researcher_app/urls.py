# researcher_app/urls.py

from django.urls import path
from .views import (
    UploadPDFView, ExtractPDFView, GenerateOutlineView,
    DraftSectionView, FormatBlogView, ChatWithPDFView,
    NormalizationRuleView, upload_page
)
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    # Backend API routes
    path('api/upload/', UploadPDFView.as_view(), name='upload-pdf'),
    path('api/extract/<int:pk>/', ExtractPDFView.as_view(), name='extract-pdf'),
    path('api/outline/<int:pk>/', GenerateOutlineView.as_view(), name='generate-outline'),
    path('api/write/<int:pk>/', DraftSectionView.as_view(), name='draft-section'),
    path('api/format/<int:pk>/', FormatBlogView.as_view(), name='format-blog'),
    path('api/chat/<int:pk>/', ChatWithPDFView.as_view(), name='chat-with-pdf'),
    path('api/rules/', NormalizationRuleView.as_view(), name='normalization-rules'),

]



# Serve media files (PDFs) during development & on Render
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
