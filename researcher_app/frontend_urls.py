from django.urls import path
from .views import (
    upload_page,
    chat_page,
    blog_page,
    ppt_page,
    poster_page,
    new_blog,
    outline_refine,
    section_write,
    blog_finish,
    blog_preview,
    blog_meta,
)

urlpatterns = [
    # Home → upload page
    path('', upload_page, name='home'),

    # Frontend pages
    path('upload/', upload_page, name='upload'),
    path('chat/<int:pdf_id>/', chat_page, name='chat-page'),

    # ——— Blog Creation Flow ———
    # 1) Kick off outline generation (opens in new tab if you add target="_blank")
    path('blog/new/<int:pdf_id>/', new_blog, name='new_blog'),
    # 2) Refine outline
    path('blog/outline/<int:outline_id>/', outline_refine, name='outline_refine'),
    # 3) Draft & refine each section
    path('blog/section/<int:outline_id>/', section_write, name='section_write'),
    # 4) Finish, add author meta data, preview & download
    path('blog/finish/<int:outline_id>/', blog_finish, name='blog_finish'),
    path('blog/meta/<int:outline_id>/', blog_meta, name='blog_meta'),
    path('blog/preview/<int:outline_id>/',blog_preview,name='blog_preview'),

    # ——— Existing “view a blog” page ———
    # (you probably want this to render the final HTML/PDF)
    path('blog/<int:pk>/', blog_page, name='blog'),

    path('ppt/<int:pk>/', ppt_page, name='ppt'),
    path('poster/<int:pk>/', poster_page, name='poster'),
]
