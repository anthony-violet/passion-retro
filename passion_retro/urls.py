"""
URL configuration for passion_retro project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import: from my_app import views
    2. Add a URL to urlpatterns: path('', views.home, name='home')
Class-based views
    1. Add an import: from other_app.views import Home
    2. Add a URL to urlpatterns: path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns: path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from . import views
from users import views as users_views
from .sitemaps import MemorySitemap, PostSitemap, StaticViewSitemap, TopicSitemap

sitemaps = {
    "static": StaticViewSitemap,
    "posts": PostSitemap,
    "topics": TopicSitemap,
    "memories": MemorySitemap,
}

urlpatterns = [
    path("admin/", admin.site.urls),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("llms.txt", views.llms_txt, name="llms_txt"),
    path("maintenance/", include("maintenance.urls")),
    path("", include("home.urls")),
    path("posts/", include("posts.urls")),
    path("forum/", include("forum.urls")),
    path("users/", include("users.urls")),
    path("guestbook/", include("guestbook.urls")),
    path("gallery/", include("gallery.urls")),
    path("games/", include("games.urls")),
    path("quiz/", include("quiz.urls")),
    path("pm/", include("messagerie.urls")),
    path("shop/", include("shop.urls")),
    path("panel/", include("panel.urls")),
    path("version/", include("version.urls")),
    path("ephemerides/", include("ephemerides.urls")),
    path("mur-des-souvenirs/", include("wall_memories.urls")),
    path("nouveautes/", users_views.announcement, name="announcement"),
    path("nouveautes/fermer/", users_views.close_announcement_banner, name="close_announcement_banner"),
    path('api/forum/', include('forum_api.urls')),

    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]

handler404 = 'home.views.custom_404'
