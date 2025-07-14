# researcher_app/urls.py

#Backend
from django.urls import path
from .views import (
    UploadPDFView, ExtractPDFView, GenerateOutlineView,
    DraftSectionView, FormatBlogView, ChatWithPDFView,
    NormalizationRuleView
)

urlpatterns = [
    path('upload/', UploadPDFView.as_view(), name='upload-pdf'),
    path('extract/<int:pk>/', ExtractPDFView.as_view(), name='extract-pdf'),
    path('outline/<int:pk>/', GenerateOutlineView.as_view(), name='generate-outline'),
    path('write/<int:pk>/', DraftSectionView.as_view(), name='draft-section'),
    path('format/<int:pk>/', FormatBlogView.as_view(), name='format-blog'),
    path('chat/<int:pk>/', ChatWithPDFView.as_view(), name='chat-with-pdf'),
    path('rules/', NormalizationRuleView.as_view(), name='normalization-rules'),
]

#Frontend
from django.urls import path
from . import views

urlpatterns = [
    # Existing API routes ...

    # 👇 Frontend routes
    path('upload/', views.upload_page, name='upload'),
]
