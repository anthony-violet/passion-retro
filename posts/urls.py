from django.urls import path
from django.conf.urls.static import static

from passion_retro import settings
from . import views

urlpatterns = [
    path("ai-assist/", views.ai_assist, name="ai_assist"),
    path("<slug:slug>/", views.view_post, name="view_post"),

    path("create/<str:type>/", views.create_post, name="create_news"),
    path("<int:post_id>/edit", views.edit_post, name="edit_post"),
]