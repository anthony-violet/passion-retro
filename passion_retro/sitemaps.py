import re
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.db.models import Exists, OuterRef, Q
from django.urls import reverse

from forum.models import Post as ForumPost
from forum.models import Topic
from posts.models import Post


_FORUM_LINK_RE = re.compile(r"^/?forum/\d+/(\d+)/?$")


def _news_topic_ids():
    """Identifiants des sujets du forum recopiés depuis une news active."""
    ids = []
    links = Post.objects.filter(active=True).exclude(forum_link__isnull=True).exclude(
        forum_link=""
    ).values_list("forum_link", flat=True)
    for link in links:
        match = _FORUM_LINK_RE.match(link)
        if match:
            ids.append(int(match.group(1)))
    return ids


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
        # Un sous-article dont le parent est désactivé n'est plus listé.
        return (
            Post.objects.filter(active=True)
            .filter(Q(post_parent__isnull=True) | Q(post_parent__active=True))
            .order_by("-updated")
        )

    def lastmod(self, obj):
        return obj.updated

    def location(self, obj):
        return reverse("view_post", args=[obj.slug])


class TopicSitemap(ConfiguredSitemap):
    priority = 0.6
    changefreq = "weekly"

    def items(self):
        return (
            Topic.objects.filter(active=True)
            # Au moins un message visible : sinon la page est vide.
            .filter(
                Exists(ForumPost.objects.filter(topic=OuterRef("pk"), active=True))
            )
            # Les sujets copiés d'une news ont pour canonical l'article :
            # seule l'URL canonique doit figurer dans le sitemap.
            .exclude(id__in=_news_topic_ids())
            .order_by("-updated")
        )

    def lastmod(self, obj):
        return obj.updated

    def location(self, obj):
        return reverse("post_list", args=[obj.forum_id, obj.id])
