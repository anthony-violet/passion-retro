from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = "weekly"

    def items(self):
        return [
            "home",
            "forum_home",
            "portal_games",
            "quiz_home",
            "gallery_home",
            "guestbook_home",
            "shop_home",
            "contribute",
        ]

    def location(self, item):
        return reverse(item)
