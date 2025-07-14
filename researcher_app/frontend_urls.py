# researcher_app/frontend_urls.py

from django.urls import path
from .views import upload_page

urlpatterns = [
    path('upload/', upload_page, name='upload'),
]
