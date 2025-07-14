# agentic_researcher/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # API endpoints (still under /api/)
    path('api/', include('researcher_app.urls')),

    # Frontend routes (no prefix)
    path('', include('researcher_app.frontend_urls')),  # <- Add this
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
