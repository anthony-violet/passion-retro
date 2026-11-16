from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from forum.models import Topic
from posts.models import Post


class _ConfiguredSite:
    def __init__(self, domain):
        self.domain = domain


class ConfiguredSitemap(Sitemap):
    """Force les URLs absolues sur SITE_URL, quel que soit l'hôte de la requête."""

    def get_urls(self, page=1, site=None, protocol=None):
        parsed = urlsplit(settings.SITE_URL)
        return super().get_urls(
            page=page,
            site=_ConfiguredSite(parsed.netloc),
            protocol=parsed.scheme or "https",
        )


class StaticViewSitemap(ConfiguredSitemap):
    priority = 0.7
    changefreq = "weekly"

    def items(self):
        return [
            "home",
            "discover",
            "forum_home",
            "portal_games",
            "guestbook_home",
            "ephemerides:ephemerides_today",
        ]

    def location(self, item):
        return reverse(item)


class PostSitemap(ConfiguredSitemap):
    priority = 0.8
    changefreq = "monthly"

    def items(self):
        return Post.objects.filter(active=True).order_by("-updated")

    def lastmod(self, obj):
        return obj.updated

    def location(self, obj):
        return reverse("view_post", args=[obj.slug])


class TopicSitemap(ConfiguredSitemap):
    priority = 0.6
    changefreq = "weekly"

    def items(self):
        return Topic.objects.filter(state="open").order_by("-updated")

    def lastmod(self, obj):
        return obj.updated

    def location(self, obj):
        return reverse("post_list", args=[obj.forum_id, obj.id])
