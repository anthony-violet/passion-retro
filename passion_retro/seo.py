import json
import re

from django.conf import settings
from django.templatetags.static import static


def _json(data):
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003C")


def _base_url():
    return settings.SITE_URL.rstrip("/")


def _logo_url():
    return f"{_base_url()}{static('img/retrobot.png')}"


def absolute_url(request, path):
    if not path:
        return None
    text = str(path)
    if text.startswith(("http://", "https://")):
        return text
    if not text.startswith("/"):
        text = f"/{text}"
    return request.build_absolute_uri(text)


def default_og_image(request):
    return request.build_absolute_uri(static("img/retrobot.png"))


def media_og_image(request, image):
    if not image:
        return default_og_image(request)
    return absolute_url(request, f"/media/{image}")


def plain_text(text, limit=160):
    text = re.sub(r"\[[^\]]*\]", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def _absolute(path):
    text = str(path)
    if text.startswith(("http://", "https://")):
        return text
    if not text.startswith("/"):
        text = f"/{text}"
    return f"{_base_url()}{text}"


def organization_data():
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": settings.SITE_NAME,
        "url": _base_url(),
        "logo": {
            "@type": "ImageObject",
            "url": _logo_url(),
        },
    }


def website_data():
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": settings.SITE_NAME,
        "url": _base_url(),
        "inLanguage": "fr-FR",
    }


def article_data(request, post):
    data = {
        "@context": "https://schema.org",
        "@type": "NewsArticle" if getattr(post, "type", "") == "news" else "Article",
        "headline": post.title,
        "description": plain_text(getattr(post, "content", ""), 200),
        "datePublished": post.created.isoformat(),
        "dateModified": post.updated.isoformat(),
        "author": {
            "@type": "Person",
            "name": post.author.username,
        },
        "publisher": {
            "@type": "Organization",
            "name": settings.SITE_NAME,
            "logo": {
                "@type": "ImageObject",
                "url": _logo_url(),
            },
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": absolute_url(request, request.path),
        },
        "inLanguage": "fr-FR",
    }
    if getattr(post, "image", None):
        data["image"] = absolute_url(request, f"/media/{post.image}")
    return data


def discussion_data(request, topic, posts_count):
    return {
        "@context": "https://schema.org",
        "@type": "DiscussionForumPosting",
        "headline": topic.title,
        "url": absolute_url(request, request.path),
        "datePublished": topic.created.isoformat(),
        "dateModified": topic.updated.isoformat(),
        "author": {
            "@type": "Person",
            "name": topic.author.username,
        },
        "interactionStatistic": {
            "@type": "InteractionCounter",
            "interactionType": "https://schema.org/CommentAction",
            "userInteractionCount": posts_count,
        },
        "inLanguage": "fr-FR",
    }


def breadcrumb_data(items):
    elements = []
    for position, (name, path) in enumerate(items, start=1):
        elements.append(
            {
                "@type": "ListItem",
                "position": position,
                "name": name,
                "item": _absolute(path),
            }
        )
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": elements,
    }


def ephemerides_data(request, events, today):
    url = absolute_url(request, request.path)
    items = []
    for position, event in enumerate(events, start=1):
        items.append(
            {
                "@type": "ListItem",
                "position": position,
                "item": {
                    "@type": "CreativeWork",
                    "name": event.title,
                    "description": plain_text(event.content, 300),
                    "temporalCoverage": f"{event.year:04d}-{event.month:02d}-{event.day:02d}",
                    "url": url,
                },
            }
        )
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": f"Éphémérides du {today.strftime('%d/%m')}",
        "itemListElement": items,
    }


def graph(*items):
    cleaned = []
    for item in items:
        if not item:
            continue
        item = dict(item)
        item.pop("@context", None)
        cleaned.append(item)
    return _json({"@context": "https://schema.org", "@graph": cleaned})


def organization_jsonld():
    return _json(organization_data())


def website_jsonld():
    return _json(website_data())


def article_jsonld(request, post, breadcrumbs=None):
    if breadcrumbs:
        return graph(article_data(request, post), breadcrumb_data(breadcrumbs))
    return _json(article_data(request, post))


def discussion_jsonld(request, topic, posts_count, breadcrumbs=None):
    if breadcrumbs:
        return graph(
            discussion_data(request, topic, posts_count),
            breadcrumb_data(breadcrumbs),
        )
    return _json(discussion_data(request, topic, posts_count))


def breadcrumb_jsonld(items):
    return _json(breadcrumb_data(items))


def ephemerides_jsonld(request, events, today):
    if not events:
        return ""
    return _json(ephemerides_data(request, events, today))
