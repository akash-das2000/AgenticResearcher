# researcher_app/frontend_urls.py

from django.urls import path
from .views import (
    upload_page,
    chat_page,
    blog_page,
    ppt_page,
    poster_page
)

urlpatterns = [
    path('upload/', upload_page, name='upload'),
    path('chat/<int:pk>/', chat_page, name='chat'),
    path('blog/<int:pk>/', blog_page, name='blog'),
    path('ppt/<int:pk>/', ppt_page, name='ppt'),
    path('poster/<int:pk>/', poster_page, name='poster'),
]
