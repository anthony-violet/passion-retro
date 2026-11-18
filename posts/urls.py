from django.urls import path
from django.conf.urls.static import static

from passion_retro import settings
from . import views

urlpatterns = [
    path("ai-assist/", views.ai_assist, name="ai_assist"),
    path("preview-content/", views.preview_content, name="preview_content"),
    path("<slug:slug>/", views.view_post, name="view_post"),
    path("<slug:slug>/reagir/", views.news_react, name="news_react"),

    path("create/<str:type>/", views.create_post, name="create_news"),
    path("<int:post_id>/edit", views.edit_post, name="edit_post"),
]